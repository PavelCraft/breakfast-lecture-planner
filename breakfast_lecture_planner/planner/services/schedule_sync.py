from django.db import transaction

from planner.models import CalendarPeriod, DailySchedule, Post
from planner.services.calendar_markers import markers_in_html
from planner.services.schedule_parser import ScheduleStructureError, parse_schedule, replace_day_content


def _sync_kartika_period(parsed):
    dates_in_source = {day.date for day in parsed.days}
    events = []
    for day in parsed.days:
        boundaries = [
            kind for kind in markers_in_html(day.content)
            if kind in {"kartika_start", "kartika_end"}
        ]
        if len(boundaries) > 1:
            raise ScheduleStructureError(
                [f"На {day.date:%d.%m.%Y} должна быть только одна граница Картики."]
            )
        if boundaries:
            events.append((day.date, boundaries[0]))

    existing = list(CalendarPeriod.objects.select_for_update().order_by("starts_on"))
    source_start = min(dates_in_source)
    carry = next(
        (
            period for period in reversed(existing)
            if period.starts_on < source_start
            and (period.ends_on is None or period.ends_on >= source_start)
        ),
        None,
    )
    open_start = carry.starts_on if carry else None
    proposed = []

    for boundary_date, kind in events:
        if kind == "kartika_start":
            if open_start is not None:
                raise ScheduleStructureError(
                    [
                        f"Новое начало Картики {boundary_date:%d.%m.%Y} указано до завершения предыдущего периода."
                    ]
                )
            open_start = boundary_date
            continue

        if open_start is None:
            raise ScheduleStructureError(
                [f"Конец Картики {boundary_date:%d.%m.%Y} указан без начала."]
            )
        if boundary_date <= open_start:
            raise ScheduleStructureError(["Конец Картики должен быть позже её начала."])
        proposed.append((open_start, boundary_date))
        open_start = None

    if open_start is not None:
        proposed.append((open_start, None))

    affected_ids = {
        period.pk for period in existing
        if period.starts_on in dates_in_source or period.ends_on in dates_in_source
    }
    if carry:
        affected_ids.add(carry.pk)
    preserved = [
        (period.starts_on, period.ends_on)
        for period in existing
        if period.pk not in affected_ids
    ]
    all_periods = sorted([*preserved, *proposed], key=lambda value: value[0])
    for previous, following in zip(all_periods, all_periods[1:]):
        if previous[1] is None or following[0] <= previous[1]:
            raise ScheduleStructureError(
                ["Периоды Картики не должны пересекаться."]
            )

    desired = dict(proposed)
    for period in existing:
        if period.pk not in affected_ids:
            continue
        if period.starts_on not in desired:
            period.delete()
            continue
        end = desired.pop(period.starts_on)
        if period.ends_on != end:
            period.ends_on = end
            period.save(update_fields=["ends_on"])
    CalendarPeriod.objects.bulk_create(
        [CalendarPeriod(starts_on=start, ends_on=end) for start, end in desired.items()]
    )


def sync_daily_schedules(post, reference_date=None):
    parsed = parse_schedule(post.content, reference_date=reference_date)
    with transaction.atomic():
        _sync_kartika_period(parsed)
        for day in parsed.days:
            DailySchedule.objects.update_or_create(
                date=day.date, defaults={"content": day.content}
            )
    return parsed


def sync_day_to_main_schedule(schedule_date, content):
    with transaction.atomic():
        post = Post.objects.select_for_update().get(pk=12)
        post.content = replace_day_content(post.content, schedule_date, content)
        parsed = parse_schedule(post.content, reference_date=schedule_date)
        _sync_kartika_period(parsed)
        post.save(update_fields=["content"])
        schedule, _ = DailySchedule.objects.update_or_create(
            date=schedule_date, defaults={"content": content}
        )
    return schedule, post

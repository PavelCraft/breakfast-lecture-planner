from django.db import models, transaction

from planner.models import CalendarPeriod, DailySchedule, Post
from planner.services.calendar_markers import markers_in_html
from planner.services.schedule_parser import ScheduleStructureError, parse_schedule, replace_day_content


def _sync_kartika_period(parsed):
    starts = [day.date for day in parsed.days for kind in markers_in_html(day.content) if kind == "kartika_start"]
    ends = [day.date for day in parsed.days for kind in markers_in_html(day.content) if kind == "kartika_end"]
    if len(starts) > 1 or len(ends) > 1:
        raise ScheduleStructureError(["У Картики должны быть не более одного начала и одного конца."])

    start = starts[0] if starts else None
    end = ends[0] if ends else None
    dates_in_source = {day.date for day in parsed.days}
    existing = None
    if start:
        existing = CalendarPeriod.objects.select_for_update().filter(year=start.year).first()
    elif end:
        existing = (
            CalendarPeriod.objects.select_for_update()
            .filter(starts_on__lt=end)
            .filter(models.Q(ends_on__isnull=True) | models.Q(ends_on__in=dates_in_source))
            .order_by("-starts_on")
            .first()
        )
        if not existing:
            raise ScheduleStructureError(["Найден конец Картики, но не найдено её начало."])

    actual_start = start or (existing.starts_on if existing else None)
    if end and end <= actual_start:
        raise ScheduleStructureError(["Конец Картики не может быть раньше её начала."])

    if start:
        CalendarPeriod.objects.update_or_create(
            year=start.year, defaults={"starts_on": start, "ends_on": end}
        )
    elif end and existing:
        existing.ends_on = end
        existing.save(update_fields=["ends_on"])

    for period in CalendarPeriod.objects.select_for_update().all():
        if not start and period.starts_on in dates_in_source:
            period.delete()
        elif not end and period.ends_on in dates_in_source:
            period.ends_on = None
            period.save(update_fields=["ends_on"])


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

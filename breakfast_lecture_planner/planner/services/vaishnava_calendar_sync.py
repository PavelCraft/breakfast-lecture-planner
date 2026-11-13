"""Two-way hashtag synchronization for the schedule and Vaišnava calendar."""

import re
from dataclasses import dataclass
from datetime import date

from bs4 import BeautifulSoup, Tag
from django.db import transaction

from planner.models import Post
from planner.services.calendar_markers import (
    MARKERS,
    markers_in_html,
    set_inline_markers,
    set_markers_in_html,
)
from planner.services.schedule_parser import ScheduleStructureError, parse_schedule, replace_day_content
from planner.services.schedule_sync import sync_daily_schedules


MONTHS = {
    "sausio": 1,
    "vasario": 2,
    "kovo": 3,
    "balandžio": 4,
    "gegužės": 5,
    "birželio": 6,
    "liepos": 7,
    "rugpjūčio": 8,
    "rugsėjo": 9,
    "spalio": 10,
    "lapkričio": 11,
    "gruodžio": 12,
}
DATE_PATTERN = re.compile(
    rf"^\s*(\d{{1,2}})\s+({'|'.join(map(re.escape, MONTHS))})\b",
    flags=re.IGNORECASE,
)
YEAR_RANGE_PATTERN = re.compile(r"\b(20\d{2})\s*[-–—]\s*(20\d{2})\b")
CANONICAL_HASHTAGS = {value.casefold() for value in MARKERS.values()}


@dataclass
class CalendarEntry:
    date: date
    tag: Tag
    markers: list[str]


@dataclass
class ParsedCalendarPage:
    soup: BeautifulSoup
    entries: dict[date, CalendarEntry]


def parse_calendar_page(html, reference_date=None):
    """Parse paragraphs such as ``20 Lapkričio ...`` across a year range."""
    soup = BeautifulSoup(html or "", "html.parser")
    plain_text = soup.get_text(" ", strip=True)
    year_match = YEAR_RANGE_PATTERN.search(plain_text)
    start_year = int(year_match.group(1)) if year_match else (reference_date or date.today()).year
    end_year = int(year_match.group(2)) if year_match else start_year + 1
    current_year = start_year
    previous_month = None
    entries = {}

    for tag in soup.find_all("p"):
        text = " ".join(tag.get_text(" ", strip=True).split())
        match = DATE_PATTERN.match(text)
        if not match:
            continue
        day_number = int(match.group(1))
        month = MONTHS[match.group(2).casefold()]
        if previous_month is not None and month < previous_month:
            current_year = min(current_year + 1, end_year)
        previous_month = month
        try:
            entry_date = date(current_year, month, day_number)
        except ValueError:
            continue
        entries.setdefault(
            entry_date,
            CalendarEntry(entry_date, tag, markers_in_html(str(tag))),
        )
    return ParsedCalendarPage(soup=soup, entries=entries)


def _remove_unbound_hashtags(calendar):
    """Remove marker-only paragraphs which cannot be associated with a date."""
    for tag in list(calendar.soup.find_all("p")):
        text = " ".join(tag.get_text(" ", strip=True).split()).casefold()
        if text in CANONICAL_HASHTAGS and not DATE_PATTERN.match(text):
            tag.decompose()


def _ordered_union(*groups):
    present = set().union(*map(set, groups))
    return [kind for kind in MARKERS if kind in present]


def _merge_marker_edit(previous, submitted, linked):
    """Apply only explicit additions/removals made in the submitted source.

    A marker absent from both the previous and submitted versions was never
    removed by this editor, so an existing marker from the linked page must be
    retained. This also makes the first synchronization of legacy content safe.
    """
    removed = set(previous) - set(submitted)
    retained_linked = set(linked) - removed
    return _ordered_union(retained_linked, submitted)


def _schedule_days(html, reference_date=None):
    parsed = parse_schedule(html, reference_date=reference_date)
    return parsed, {day.date: day for day in parsed.days}


def _replace_schedule_markers(html, changes, reference_date=None):
    updated = html
    for schedule_date, kinds in sorted(changes.items()):
        parsed = parse_schedule(updated, reference_date=reference_date or schedule_date)
        day = next(day for day in parsed.days if day.date == schedule_date)
        updated = replace_day_content(
            updated,
            schedule_date,
            set_markers_in_html(day.content, kinds),
            reference_date=reference_date or schedule_date,
        )
    return updated


@transaction.atomic
def sync_calendar_post_to_main(calendar_post, previous_content, reference_date=None):
    """Apply edits from Post 14; new dates inherit existing schedule hashtags."""
    calendar_post = Post.objects.select_for_update().get(pk=calendar_post.pk)
    main_post = Post.objects.select_for_update().get(pk=12)
    old_calendar = parse_calendar_page(previous_content, reference_date)
    new_calendar = parse_calendar_page(calendar_post.content, reference_date)
    _remove_unbound_hashtags(new_calendar)
    _, main_days = _schedule_days(main_post.content, reference_date)
    main_changes = {}

    for entry_date, entry in new_calendar.entries.items():
        main_kinds = markers_in_html(main_days[entry_date].content) if entry_date in main_days else []
        previous_kinds = (
            old_calendar.entries[entry_date].markers
            if entry_date in old_calendar.entries
            else []
        )
        desired = _merge_marker_edit(previous_kinds, entry.markers, main_kinds)
        set_inline_markers(entry.tag, desired)
        if entry_date in main_days and set(main_kinds) != set(desired):
            main_changes[entry_date] = desired

    calendar_post.content = str(new_calendar.soup)
    calendar_post.save(update_fields=["content"])
    if main_changes:
        main_post.content = _replace_schedule_markers(
            main_post.content, main_changes, reference_date
        )
        main_post.save(update_fields=["content"])
    sync_daily_schedules(main_post, reference_date=reference_date)
    return calendar_post, main_post


@transaction.atomic
def sync_main_post_to_calendar(main_post, previous_content, reference_date=None):
    """Apply edits from Post 12; newly added days inherit calendar hashtags."""
    main_post = Post.objects.select_for_update().get(pk=main_post.pk)
    try:
        _, old_days = _schedule_days(previous_content, reference_date)
    except ScheduleStructureError:
        old_days = {}
    _, new_days = _schedule_days(main_post.content, reference_date)
    calendar_post = Post.objects.select_for_update().filter(pk=14).first()
    calendar = parse_calendar_page(calendar_post.content, reference_date) if calendar_post else None
    if calendar:
        _remove_unbound_hashtags(calendar)
    main_changes = {}

    for entry_date, day in new_days.items():
        main_kinds = markers_in_html(day.content)
        previous_kinds = (
            markers_in_html(old_days[entry_date].content)
            if entry_date in old_days
            else []
        )
        calendar_entry = calendar.entries.get(entry_date) if calendar else None
        calendar_kinds = calendar_entry.markers if calendar_entry else []
        desired = _merge_marker_edit(previous_kinds, main_kinds, calendar_kinds)
        # Normalize every saved day even when its category set did not change:
        # known hashtags belong at the beginning, one paragraph per hashtag.
        main_changes[entry_date] = desired
        if calendar_entry:
            set_inline_markers(calendar_entry.tag, desired)

    main_post.content = _replace_schedule_markers(
        main_post.content, main_changes, reference_date
    )
    main_post.save(update_fields=["content"])
    if calendar_post:
        calendar_post.content = str(calendar.soup)
        calendar_post.save(update_fields=["content"])
    sync_daily_schedules(main_post, reference_date=reference_date)
    return main_post, calendar_post


def sync_date_to_calendar(schedule_date, kinds, reference_date=None):
    """Update an existing calendar entry; absence of that date is harmless."""
    calendar_post = Post.objects.select_for_update().filter(pk=14).first()
    if not calendar_post:
        return None
    calendar = parse_calendar_page(calendar_post.content, reference_date)
    entry = calendar.entries.get(schedule_date)
    if not entry:
        return calendar_post
    set_inline_markers(entry.tag, kinds)
    calendar_post.content = str(calendar.soup)
    calendar_post.save(update_fields=["content"])
    return calendar_post

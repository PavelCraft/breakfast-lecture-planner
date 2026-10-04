import re
from dataclasses import dataclass
from datetime import date, timedelta

from bs4 import BeautifulSoup, Tag


DAY_MARKER = re.compile(
    r"^(\d{1,2})\s*d\s*\.\s*(pirmadienis|antradienis|trečiadienis|ketvirtadienis|penktadienis|šeštadienis|sekmadienis)$",
    re.I,
)
WEEKDAYS = {
    "pirmadienis": 0,
    "antradienis": 1,
    "trečiadienis": 2,
    "ketvirtadienis": 3,
    "penktadienis": 4,
    "šeštadienis": 5,
    "sekmadienis": 6,
}
WEEK_SEPARATORS = ("-", "‐", "‑", "‒", "–", "—", "―", "−", "№", "#", "no", "n°")


class ScheduleStructureError(ValueError):
    def __init__(self, messages):
        self.messages = list(messages)
        super().__init__("\n".join(self.messages))


@dataclass(frozen=True)
class ParsedDay:
    date: date
    content: str


@dataclass
class ParsedSchedule:
    soup: BeautifulSoup
    days: list[ParsedDay]
    week_blocks: list[tuple[date, list[Tag]]]


def _text(tag):
    return " ".join(tag.get_text(" ", strip=True).split())


def parse_week_number(text):
    compact = "".join(text.casefold().split())
    for prefix in ("savaitė", "savaite"):
        if not compact.startswith(prefix):
            continue
        remainder = compact[len(prefix) :]
        for separator in WEEK_SEPARATORS:
            if remainder.startswith(separator):
                number = remainder[len(separator) :]
                if number.isdigit() and 1 <= len(number) <= 2:
                    return int(number)
    return None


def _top_level_tag(tag, soup):
    current = tag
    while current.parent is not soup and isinstance(current.parent, Tag):
        current = current.parent
    return current


def _without_trailing_week_separator(nodes):
    """Exclude an <hr> and empty spacer headings placed between two weeks."""
    separator = len(nodes)
    while separator and nodes[separator - 1].name != "hr" and not _text(nodes[separator - 1]):
        separator -= 1
    if separator and nodes[separator - 1].name == "hr":
        return nodes[: separator - 1]
    return nodes


def _week_monday(week_number, reference):
    candidates = []
    for year in range(reference.year - 1, reference.year + 2):
        try:
            monday = date.fromisocalendar(year, week_number, 1)
        except ValueError:
            continue
        candidates.append(monday)
    if not candidates:
        raise ScheduleStructureError(
            [f"Неделя №{week_number} не существует ни в одном из ближайших лет."]
        )
    current_monday = reference - timedelta(days=reference.weekday())
    return min(candidates, key=lambda value: abs((value - current_monday).days))


def parse_schedule(html, reference_date=None):
    reference_date = reference_date or date.today()
    soup = BeautifulSoup(html or "", "html.parser")
    top_tags = [node for node in soup.contents if isinstance(node, Tag)]
    week_markers = []
    for tag in soup.find_all(True):
        number = parse_week_number(_text(tag))
        if number and not any(
            parse_week_number(_text(child)) for child in tag.find_all(True)
        ):
            week_markers.append((_top_level_tag(tag, soup), number))

    # Один и тот же маркер может совпасть с несколькими предками; оставляем самый внутренний.
    unique_weeks = []
    for marker in week_markers:
        if marker not in unique_weeks:
            unique_weeks.append(marker)
    week_markers = unique_weeks
    errors = []
    if not week_markers:
        raise ScheduleStructureError(
            ["Не найдено ни одного маркера недели вида «savaitė — 33»."]
        )

    marker_positions = []
    for marker, number in week_markers:
        try:
            marker_positions.append((top_tags.index(marker), marker, number))
        except ValueError:
            errors.append(
                f"Не удалось безопасно определить границу недели «{_text(marker)}»."
            )
    marker_positions.sort(key=lambda item: item[0])
    days = []
    week_blocks = []
    previous_monday = None
    for index, (start, marker, number) in enumerate(marker_positions):
        end = (
            marker_positions[index + 1][0]
            if index + 1 < len(marker_positions)
            else len(top_tags)
        )
        monday = _week_monday(number, reference_date)
        if previous_monday and monday <= previous_monday:
            while monday <= previous_monday:
                try:
                    monday = date.fromisocalendar(monday.year + 1, number, 1)
                except ValueError:
                    break
        previous_monday = monday
        block = top_tags[start:end]
        week_blocks.append((monday, block))
        day_positions = []
        for offset, node in enumerate(block):
            candidates = [node, *node.find_all(True)]
            for candidate in candidates:
                match = DAY_MARKER.fullmatch(_text(candidate).casefold())
                if match:
                    day_positions.append((offset, candidate, match))
                    break
        if len(day_positions) != 7:
            errors.append(
                f"В неделе №{number} найдено {len(day_positions)} дней вместо 7."
            )
            continue
        seen_weekdays = set()
        for day_index, (position, heading, match) in enumerate(day_positions):
            day_number = int(match.group(1))
            weekday = WEEKDAYS[match.group(2).casefold()]
            expected = monday + timedelta(days=weekday)
            if weekday in seen_weekdays:
                errors.append(
                    f"В неделе №{number} день «{match.group(2)}» указан дважды."
                )
            seen_weekdays.add(weekday)
            if expected.day != day_number:
                errors.append(
                    f"В неделе №{number} заголовок «{_text(heading)}» не совпадает с датой {expected:%d.%m.%Y}."
                )
            next_position = (
                day_positions[day_index + 1][0] if day_index + 1 < 7 else len(block)
            )
            content_nodes = block[position + 1 : next_position]
            if day_index == len(day_positions) - 1:
                content_nodes = _without_trailing_week_separator(content_nodes)
            content = "".join(str(node) for node in content_nodes).strip()
            days.append(ParsedDay(expected, content))
    current_monday = reference_date - timedelta(days=reference_date.weekday())
    if not any(monday == current_monday for monday, _ in week_blocks):
        errors.append(
            f"Не найдено расписание текущей недели, начинающейся {current_monday:%d.%m.%Y}."
        )
    if errors:
        raise ScheduleStructureError(errors)
    return ParsedSchedule(soup=soup, days=days, week_blocks=week_blocks)


def replace_day_content(html, target_date, new_content, reference_date=None):
    parsed = parse_schedule(html, reference_date=reference_date or target_date)
    target = next((day for day in parsed.days if day.date == target_date), None)
    if not target:
        raise ScheduleStructureError(
            [f"В большом расписании нет дня {target_date:%d.%m.%Y}."]
        )

    # Повторно ищем границы на верхнем уровне и заменяем только тело дня.
    soup = BeautifulSoup(html or "", "html.parser")
    top_tags = [node for node in soup.contents if isinstance(node, Tag)]
    headings = []
    for index, node in enumerate(top_tags):
        for candidate in [node, *node.find_all(True)]:
            match = DAY_MARKER.fullmatch(_text(candidate).casefold())
            if match:
                headings.append((index, match))
                break
    parsed_dates = [day.date for day in parsed.days]
    target_index = parsed_dates.index(target_date)
    start = headings[target_index][0]
    next_heading = (
        headings[target_index + 1][0]
        if target_index + 1 < len(headings)
        else len(top_tags)
    )
    # The marker of the next week sits between Sunday and the following Monday.
    # It belongs to neither day's body and must survive a Sunday edit.
    next_week_marker = next(
        (
            index
            for index, node in enumerate(top_tags[start + 1 :], start=start + 1)
            if parse_week_number(_text(node)) is not None
        ),
        len(top_tags),
    )
    end = min(next_heading, next_week_marker)
    day_nodes = top_tags[start + 1 : end]
    end = start + 1 + len(_without_trailing_week_separator(day_nodes))
    for node in top_tags[start + 1 : end]:
        node.extract()
    anchor = top_tags[start]
    fragment = BeautifulSoup(new_content or "", "html.parser")
    for node in reversed(list(fragment.contents)):
        anchor.insert_after(node)
    return str(soup)

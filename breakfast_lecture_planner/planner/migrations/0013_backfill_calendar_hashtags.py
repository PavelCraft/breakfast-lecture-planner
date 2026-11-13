import re
from datetime import date

from bs4 import BeautifulSoup, NavigableString
from django.db import migrations


MARKERS = (
    "#Ekadaši",
    "#Pasninkas",
    "#Šventės",
    "#ŠventųjųDienos",
    "#KartikaPradžia",
    "#KartikaPabaiga",
)
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


def backfill_calendar_hashtags(apps, schema_editor):
    Post = apps.get_model("planner", "Post")
    DailySchedule = apps.get_model("planner", "DailySchedule")
    calendar = Post.objects.filter(pk=14).first()
    if not calendar:
        return

    soup = BeautifulSoup(calendar.content or "", "html.parser")
    year_match = YEAR_RANGE_PATTERN.search(soup.get_text(" ", strip=True))
    if not year_match:
        return
    current_year = int(year_match.group(1))
    end_year = int(year_match.group(2))
    previous_month = None
    schedules = {
        schedule.date: schedule.content or ""
        for schedule in DailySchedule.objects.all().only("date", "content")
    }
    changed = False

    for tag in soup.find_all("p"):
        text = " ".join(tag.get_text(" ", strip=True).split())
        if text.casefold() in {marker.casefold() for marker in MARKERS}:
            tag.decompose()
            changed = True
            continue
        match = DATE_PATTERN.match(text)
        if not match:
            continue
        month = MONTHS[match.group(2).casefold()]
        if previous_month is not None and month < previous_month:
            current_year = min(current_year + 1, end_year)
        previous_month = month
        try:
            entry_date = date(current_year, month, int(match.group(1)))
        except ValueError:
            continue

        daily_content = schedules.get(entry_date, "")
        missing = [
            marker
            for marker in MARKERS
            if re.search(
                rf"(?<![\w#]){re.escape(marker)}(?!\w)",
                daily_content,
                flags=re.IGNORECASE,
            )
            and marker.casefold() not in text.casefold()
        ]
        if missing:
            tag.append(NavigableString(" " + " ".join(missing)))
            changed = True

    if changed:
        calendar.content = str(soup)
        calendar.save(update_fields=["content"])


class Migration(migrations.Migration):
    dependencies = [("planner", "0012_calendar_hashtags")]

    operations = [
        migrations.RunPython(backfill_calendar_hashtags, migrations.RunPython.noop),
    ]

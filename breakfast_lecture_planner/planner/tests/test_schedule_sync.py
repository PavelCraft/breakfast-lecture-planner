from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from planner.models import CalendarPeriod, DailySchedule, Post
from planner.services.calendar_markers import categories_in_html, decorated_main_content, public_day_content
from planner.services.schedule_parser import (
    parse_schedule,
    parse_week_number,
    replace_day_content,
)
from planner.services.schedule_archive import archive_previous_week


WEEKDAYS = [
    "Pirmadienis",
    "Antradienis",
    "Trečiadienis",
    "Ketvirtadienis",
    "Penktadienis",
    "Šeštadienis",
    "Sekmadienis",
]


def week_html(year, week, wrapped=False):
    heading = f'<h2 style="margin-left:0">SAVAITĖ № {week}</h2>'
    if wrapped:
        heading = f"<blockquote>{heading}</blockquote>"
    days = []
    for weekday, name in enumerate(WEEKDAYS, start=1):
        value = date.fromisocalendar(year, week, weekday)
        days.append(
            f'<h6 style="margin-left:0">{value.day} d. {name}</h6><p>day-{weekday}</p>'
        )
    return heading + "".join(days)


class ScheduleParserTests(TestCase):
    def test_accepts_tolerant_week_markers_without_regular_expression(self):
        for marker in ("savaitė—33", "SAVAITĖ - 33", "savaitė № 33", "savaite#33"):
            self.assertEqual(parse_week_number(marker), 33)

    def test_resolves_previous_year_week_before_week_one(self):
        content = week_html(2025, 52, wrapped=True) + week_html(2026, 1)
        parsed = parse_schedule(content, reference_date=date(2026, 1, 2))
        self.assertEqual(parsed.days[0].date, date(2025, 12, 22))
        self.assertEqual(parsed.days[-1].date, date(2026, 1, 4))

    def test_replaces_only_selected_day_body(self):
        content = week_html(2026, 1)
        changed = replace_day_content(
            content, date(2026, 1, 2), "<ul><li>Changed</li></ul>"
        )
        parsed = parse_schedule(changed, reference_date=date(2026, 1, 2))
        self.assertEqual(parsed.days[4].content, "<ul><li>Changed</li></ul>")
        self.assertEqual(parsed.days[3].content, "<p>day-4</p>")

    def test_calendar_markers_are_standalone_and_hidden_only_in_daily_card(self):
        content = "<p>[Экадаши]</p><p>[Пост]</p><p>Текст [Праздник] внутри записи</p>"
        self.assertEqual(categories_in_html(content), ["ekadashi", "fast"])
        self.assertNotIn("[Экадаши]", public_day_content(content))
        self.assertIn("Текст [Праздник]", public_day_content(content))
        self.assertIn("schedule-marker--ekadashi", decorated_main_content(content))


class ScheduleEditingTests(TestCase):
    def setUp(self):
        group = Group.objects.create(name="Админ")
        self.user = get_user_model().objects.create_user("admin", password="secret")
        self.user.groups.add(group)
        today = timezone.localdate()
        iso_year, iso_week, _ = today.isocalendar()
        self.content = week_html(iso_year, iso_week)
        Post.objects.create(pk=12, title="Schedule", content=self.content)
        Post.objects.create(pk=17, title="Archive", content="<p>Old archive</p>")
        self.first = Client()
        self.second = Client()
        self.first.force_login(self.user)
        self.second.force_login(self.user)

    def test_second_tab_cannot_acquire_lock(self):
        url = reverse("planner:schedule_edit_lock")
        self.assertEqual(
            self.first.post(url, {"action": "acquire", "token": "first"}).status_code,
            200,
        )
        self.assertEqual(
            self.second.post(url, {"action": "acquire", "token": "second"}).status_code,
            409,
        )
        self.first.post(url, {"action": "release", "token": "first"})
        self.assertEqual(
            self.second.post(url, {"action": "acquire", "token": "second"}).status_code,
            200,
        )

    def test_editor_gets_fresh_content_after_another_tab_saved(self):
        lock_url = reverse("planner:schedule_edit_lock")
        edit_url = reverse("planner:post-edit", args=[12])
        changed = self.content.replace("<p>day-1</p>", "<p>Fresh value</p>")
        self.first.post(lock_url, {"action": "acquire", "token": "first"})
        self.first.post(
            edit_url,
            {"content": changed, "edit_lock_token": "first"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.first.post(lock_url, {"action": "release", "token": "first"})
        self.second.post(lock_url, {"action": "acquire", "token": "second"})

        response = self.second.get(
            edit_url, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], changed)
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")

        daily_response = self.second.get(
            reverse("planner:daily_schedule"),
            {"date": timezone.localdate().isoformat()},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(daily_response.headers["Cache-Control"], "no-store, private")

    def test_big_schedule_updates_daily_rows(self):
        lock_url = reverse("planner:schedule_edit_lock")
        self.first.post(lock_url, {"action": "acquire", "token": "first"})
        response = self.first.post(
            reverse("planner:post-edit", args=[12]),
            {"content": self.content, "edit_lock_token": "first"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DailySchedule.objects.count(), 7)

    def test_kartika_start_without_end_remains_open(self):
        start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        marked = self.content.replace("<p>day-1</p>", "<p>[Картика: начало]</p><p>day-1</p>")
        post = Post.objects.get(pk=12)
        post.content = marked
        post.save(update_fields=["content"])
        from planner.services.schedule_sync import sync_daily_schedules
        sync_daily_schedules(post)
        period = CalendarPeriod.objects.get(year=start.year)
        self.assertEqual(period.starts_on, start)
        self.assertIsNone(period.ends_on)

        response = self.first.get(reverse("planner:daily_schedule"), {"date": start.isoformat()})
        self.assertTrue(response.json()["kartika"])
        self.assertNotIn("[Картика: начало]", response.json()["content"])

        post.content = self.content
        post.save(update_fields=["content"])
        sync_daily_schedules(post)
        self.assertFalse(CalendarPeriod.objects.exists())

    def test_kartika_end_before_start_does_not_update_daily_rows(self):
        marked = self.content.replace("<p>day-1</p>", "<p>[Картика: конец]</p><p>day-1</p>")
        marked = marked.replace("<p>day-2</p>", "<p>[Картика: начало]</p><p>day-2</p>")
        self.first.post(reverse("planner:schedule_edit_lock"), {"action": "acquire", "token": "first"})
        response = self.first.post(
            reverse("planner:post-edit", args=[12]),
            {"content": marked, "edit_lock_token": "first"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertIn("Конец Картики", response.json()["warning"])
        self.assertFalse(CalendarPeriod.objects.exists())

    def test_daily_marker_edit_updates_metadata_and_hides_marker_from_card(self):
        today = timezone.localdate()
        self.first.post(reverse("planner:schedule_edit_lock"), {"action": "acquire", "token": "first"})
        response = self.first.post(
            reverse("planner:daily_schedule"),
            {
                "date": today.isoformat(),
                "daily-content": "<p>[Экадаши]</p><p>[Праздник]</p><p>Program</p>",
                "edit_lock_token": "first",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["categories"], ["ekadashi", "holiday"])
        self.assertNotIn("[Экадаши]", response.json()["content"])
        self.assertIn("schedule-marker--ekadashi", response.json()["main_content"])
        self.assertIn("[Экадаши]", Post.objects.get(pk=12).content)
        self.assertIn(
            "schedule-marker--ekadashi",
            self.first.get(reverse("planner:new")).content.decode(),
        )
        public = Client().get(reverse("planner:daily_schedule"), {"date": today.isoformat()}).json()
        self.assertEqual(public["raw_content"], "")
        self.assertNotIn("[Экадаши]", public["content"])

    def test_big_editor_adds_and_removes_daily_categories(self):
        today = timezone.localdate()
        self.first.post(reverse("planner:schedule_edit_lock"), {"action": "acquire", "token": "first"})
        edit_url = reverse("planner:post-edit", args=[12])
        daily_url = reverse("planner:daily_schedule")
        marked = self.content.replace(
            f"<p>day-{today.isoweekday()}</p>",
            f"<p>[Экадаши]</p><p>day-{today.isoweekday()}</p>",
        )
        response = self.first.post(
            edit_url,
            {"content": marked, "edit_lock_token": "first"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["warning"])
        self.assertEqual(
            self.first.get(daily_url, {"date": today.isoformat()}).json()["categories"],
            ["ekadashi"],
        )

        response = self.first.post(
            edit_url,
            {"content": self.content, "edit_lock_token": "first"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["warning"])
        self.assertEqual(
            self.first.get(daily_url, {"date": today.isoformat()}).json()["categories"],
            [],
        )

    def test_service_markers_are_highlighted_for_admin_but_hidden_from_public_home(self):
        post = Post.objects.get(pk=12)
        post.content = self.content.replace("<p>day-1</p>", "<p>[Экадаши]</p><p>day-1</p>")
        post.save(update_fields=["content"])
        admin_html = self.first.get(reverse("planner:new")).content.decode()
        self.assertIn("schedule-marker--ekadashi", admin_html)
        self.assertIn('id="today"', admin_html)
        self.assertNotIn("[Экадаши]", Client().get(reverse("planner:new")).content.decode())

    def test_kartika_boundaries_can_be_set_in_separate_day_editors(self):
        monday = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        tuesday = monday + timedelta(days=1)
        self.first.post(reverse("planner:schedule_edit_lock"), {"action": "acquire", "token": "first"})
        url = reverse("planner:daily_schedule")
        for value, marker in (
            (monday, "[Картика: начало]"),
            (tuesday, "[Картика: конец]"),
        ):
            response = self.first.post(
                url,
                {
                    "date": value.isoformat(),
                    "daily-content": f"<p>{marker}</p><p>Program</p>",
                    "edit_lock_token": "first",
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(response.status_code, 200, response.content)
        period = CalendarPeriod.objects.get(year=monday.year)
        self.assertEqual(period.starts_on, monday)
        self.assertEqual(period.ends_on, tuesday)
        self.assertFalse(self.first.get(url, {"date": (tuesday + timedelta(days=1)).isoformat()}).json()["kartika"])

    def test_archiving_does_not_erase_open_kartika_period(self):
        today = timezone.localdate()
        current_monday = today - timedelta(days=today.weekday())
        previous_monday = current_monday - timedelta(days=7)
        previous_year, previous_week, _ = previous_monday.isocalendar()
        current_year, current_week, _ = current_monday.isocalendar()
        previous = week_html(previous_year, previous_week).replace(
            "<p>day-1</p>", "<p>[Картика: начало]</p><p>day-1</p>"
        )
        post = Post.objects.get(pk=12)
        post.content = previous + week_html(current_year, current_week)
        post.save(update_fields=["content"])
        from planner.services.schedule_sync import sync_daily_schedules
        sync_daily_schedules(post)

        archive_previous_week(reference_date=today)
        period = CalendarPeriod.objects.get(year=previous_monday.year)
        self.assertEqual(period.starts_on, previous_monday)
        self.assertIsNone(period.ends_on)
        response = self.first.get(
            reverse("planner:daily_schedule"), {"date": current_monday.isoformat()}
        )
        self.assertTrue(response.json()["kartika"])
        self.first.post(reverse("planner:schedule_edit_lock"), {"action": "acquire", "token": "first"})
        end_response = self.first.post(
            reverse("planner:daily_schedule"),
            {
                "date": current_monday.isoformat(),
                "daily-content": "<p>[Картика: конец]</p><p>Program</p>",
                "edit_lock_token": "first",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(end_response.status_code, 200, end_response.content)
        period.refresh_from_db()
        self.assertEqual(period.ends_on, current_monday)

    def test_invalid_big_text_is_saved_without_changing_daily_rows(self):
        today = timezone.localdate()
        DailySchedule.objects.create(date=today, content="<p>Published</p>")
        lock_url = reverse("planner:schedule_edit_lock")
        self.first.post(lock_url, {"action": "acquire", "token": "first"})
        response = self.first.post(
            reverse("planner:post-edit", args=[12]),
            {"content": "<p>savanna — 33</p>", "edit_lock_token": "first"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["warning"])
        self.assertEqual(Post.objects.get(pk=12).content, "<p>savanna — 33</p>")
        self.assertEqual(
            DailySchedule.objects.get(date=today).content, "<p>Published</p>"
        )

    def test_daily_edit_updates_big_schedule(self):
        today = timezone.localdate()
        lock_url = reverse("planner:schedule_edit_lock")
        self.first.post(lock_url, {"action": "acquire", "token": "first"})
        response = self.first.post(
            reverse("planner:daily_schedule"),
            {
                "date": today.isoformat(),
                "daily-content": "<p>Updated in calendar</p>",
                "edit_lock_token": "first",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("Updated in calendar", Post.objects.get(pk=12).content)

    def test_archives_past_week_and_keeps_daily_history(self):
        today = timezone.localdate()
        current_monday = today - timedelta(days=today.weekday())
        previous_monday = current_monday - timedelta(days=7)
        previous_year, previous_week, _ = previous_monday.isocalendar()
        current_year, current_week, _ = current_monday.isocalendar()
        source = Post.objects.get(pk=12)
        source.content = week_html(previous_year, previous_week) + week_html(
            current_year, current_week
        )
        source.save(update_fields=["content"])
        DailySchedule.objects.create(date=previous_monday, content="<p>History</p>")

        self.assertEqual(archive_previous_week(reference_date=today), 1)
        self.assertNotIn(f"№ {previous_week}</h2>", Post.objects.get(pk=12).content)
        self.assertIn(f"№ {previous_week}</h2>", Post.objects.get(pk=17).content)
        self.assertTrue(DailySchedule.objects.filter(date=previous_monday).exists())

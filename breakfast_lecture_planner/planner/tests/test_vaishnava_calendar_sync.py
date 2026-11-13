from datetime import date
from importlib import import_module

from django.apps import apps

from django.test import TestCase

from planner.models import DailySchedule, Post
from planner.services.calendar_markers import categories_in_html
from planner.services.schedule_parser import parse_schedule
from planner.services.schedule_sync import sync_day_to_main_schedule
from planner.services.vaishnava_calendar_sync import (
    parse_calendar_page,
    sync_calendar_post_to_main,
    sync_main_post_to_calendar,
)
from planner.tests.test_schedule_sync import week_html


def calendar_html(*entries):
    paragraphs = "".join(f"<p>{value}</p>" for value in entries)
    return f"<h2>Vaišnavų Kalendorius 2026-2027</h2>{paragraphs}"


class VaishnavaCalendarParserTests(TestCase):
    def test_parses_lithuanian_months_across_year_boundary(self):
        parsed = parse_calendar_page(calendar_html(
            "26 Spalio Pr Įvykis #Šventės",
            "3 Sausio S Įvykis #Ekadaši",
        ))

        self.assertEqual(list(parsed.entries), [date(2026, 10, 26), date(2027, 1, 3)])
        self.assertEqual(parsed.entries[date(2026, 10, 26)].markers, ["holiday"])
        self.assertEqual(parsed.entries[date(2027, 1, 3)].markers, ["ekadashi"])

    def test_data_migration_backfills_existing_daily_hashtags(self):
        Post.objects.create(
            pk=14,
            title="Calendar",
            content=calendar_html("13 Lapkričio Pn Įvykis", "#Pasninkas"),
        )
        DailySchedule.objects.create(
            date=date(2026, 11, 13),
            content="<p>#Pasninkas</p><p>Programa</p>",
        )
        migration = import_module(
            "planner.migrations.0013_backfill_calendar_hashtags"
        )

        migration.backfill_calendar_hashtags(apps, None)

        calendar = Post.objects.get(pk=14)
        entry = parse_calendar_page(calendar.content).entries[date(2026, 11, 13)]
        self.assertEqual(entry.markers, ["fast"])
        self.assertEqual(calendar.content.count("#Pasninkas"), 1)


class VaishnavaCalendarSynchronizationTests(TestCase):
    reference = date(2026, 10, 27)

    def setUp(self):
        self.monday = date(2026, 10, 26)

    def test_new_calendar_date_without_hashtag_inherits_main_schedule(self):
        main_content = week_html(2026, 44).replace(
            "<p>day-1</p>", "<p>#Ekadaši</p><p>day-1</p>"
        )
        Post.objects.create(pk=12, title="Schedule", content=main_content)
        old_content = calendar_html("3 Lapkričio A Kitas įvykis")
        calendar = Post.objects.create(pk=14, title="Calendar", content=old_content)
        calendar.content = calendar_html(
            "26 Spalio Pr Naujas įvykis",
            "3 Lapkričio A Kitas įvykis",
        )
        calendar.save(update_fields=["content"])

        calendar, _ = sync_calendar_post_to_main(
            calendar, old_content, reference_date=self.reference
        )

        self.assertIn("#Ekadaši", calendar.content)
        self.assertEqual(
            categories_in_html(DailySchedule.objects.get(date=self.monday).content),
            ["ekadashi"],
        )

    def test_removing_hashtag_from_existing_calendar_date_removes_it_everywhere(self):
        marked_main = week_html(2026, 44).replace(
            "<p>day-1</p>", "<p>#Ekadaši</p><p>day-1</p>"
        )
        Post.objects.create(pk=12, title="Schedule", content=marked_main)
        old_content = calendar_html("26 Spalio Pr Įvykis #Ekadaši")
        calendar = Post.objects.create(
            pk=14,
            title="Calendar",
            content=calendar_html("26 Spalio Pr Įvykis"),
        )

        sync_calendar_post_to_main(calendar, old_content, reference_date=self.reference)

        main = Post.objects.get(pk=12)
        day = parse_schedule(main.content, reference_date=self.reference).days[0]
        self.assertEqual(categories_in_html(day.content), [])
        self.assertEqual(categories_in_html(DailySchedule.objects.get(date=self.monday).content), [])

    def test_first_calendar_sync_does_not_treat_an_absent_hashtag_as_removal(self):
        main_content = week_html(2026, 44) + week_html(2026, 45)
        second_tuesday = main_content.rfind("<p>day-2</p>")
        main_content = (
            main_content[:second_tuesday]
            + "<p>#KartikaPradžia</p><p>day-2</p>"
            + main_content[second_tuesday + len("<p>day-2</p>"):]
        )
        # The second Saturday belongs to week 45 (7 November).
        second_saturday = main_content.rfind("<p>day-6</p>")
        main_content = (
            main_content[:second_saturday]
            + "<p>#KartikaPabaiga</p><p>day-6</p>"
            + main_content[second_saturday + len("<p>day-6</p>"):]
        )
        Post.objects.create(pk=12, title="Schedule", content=main_content)
        old_content = calendar_html("3 Lapkričio A Įvykis")
        calendar = Post.objects.create(pk=14, title="Calendar", content=old_content)

        calendar, main = sync_calendar_post_to_main(
            calendar,
            old_content,
            reference_date=self.reference,
        )

        self.assertIn("#KartikaPradžia", calendar.content)
        self.assertIn("#KartikaPradžia", main.content)
        self.assertIn("#KartikaPabaiga", main.content)

    def test_new_main_day_inherits_calendar_hashtag(self):
        old_main = week_html(2026, 44)
        main = Post.objects.create(
            pk=12,
            title="Schedule",
            content=old_main + week_html(2026, 45),
        )
        Post.objects.create(
            pk=14,
            title="Calendar",
            content=calendar_html("3 Lapkričio A Įvykis #ŠventųjųDienos"),
        )

        main, _ = sync_main_post_to_calendar(
            main, old_main, reference_date=self.reference
        )

        november_third = date(2026, 11, 3)
        day = next(
            day for day in parse_schedule(main.content, self.reference).days
            if day.date == november_third
        )
        self.assertEqual(categories_in_html(day.content), ["saints"])
        self.assertEqual(
            categories_in_html(DailySchedule.objects.get(date=november_third).content),
            ["saints"],
        )

    def test_first_main_sync_preserves_a_calendar_hashtag(self):
        old_main = week_html(2026, 44)
        main = Post.objects.create(pk=12, title="Schedule", content=old_main)
        Post.objects.create(
            pk=14,
            title="Calendar",
            content=calendar_html("26 Spalio Pr Įvykis #Šventės"),
        )

        main, calendar = sync_main_post_to_calendar(
            main,
            old_main,
            reference_date=self.reference,
        )

        self.assertIn("#Šventės", main.content)
        self.assertIn("#Šventės", calendar.content)

    def test_removing_main_hashtag_updates_existing_calendar_date(self):
        old_main = week_html(2026, 44).replace(
            "<p>day-1</p>", "<p>#Pasninkas</p><p>day-1</p>"
        )
        main = Post.objects.create(pk=12, title="Schedule", content=week_html(2026, 44))
        calendar = Post.objects.create(
            pk=14,
            title="Calendar",
            content=calendar_html("26 Spalio Pr Įvykis #Pasninkas"),
        )

        _, calendar = sync_main_post_to_calendar(
            main, old_main, reference_date=self.reference
        )

        self.assertNotIn("#Pasninkas", calendar.content)

    def test_daily_editor_updates_existing_calendar_date(self):
        main = Post.objects.create(
            pk=12,
            title="Schedule",
            content=week_html(2026, 44),
        )
        Post.objects.create(
            pk=14,
            title="Calendar",
            content=calendar_html("26 Spalio Pr Įvykis"),
        )

        sync_day_to_main_schedule(
            self.monday,
            "<p>#Šventės</p><p>Atnaujinta diena</p>",
        )

        main.refresh_from_db()
        calendar = Post.objects.get(pk=14)
        self.assertIn("#Šventės", calendar.content)
        self.assertEqual(
            categories_in_html(
                parse_schedule(main.content, reference_date=self.reference).days[0].content
            ),
            ["holiday"],
        )

    def test_calendar_date_absent_from_main_schedule_is_harmless(self):
        Post.objects.create(
            pk=12,
            title="Schedule",
            content=week_html(2026, 44),
        )
        old_content = calendar_html("3 Lapkričio A Įvykis")
        calendar = Post.objects.create(
            pk=14,
            title="Calendar",
            content=calendar_html("3 Lapkričio A Įvykis #Pasninkas"),
        )

        calendar, main = sync_calendar_post_to_main(
            calendar,
            old_content,
            reference_date=self.reference,
        )

        self.assertIn("#Pasninkas", calendar.content)
        self.assertNotIn("#Pasninkas", main.content)

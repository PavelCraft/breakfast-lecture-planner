from importlib import import_module
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from planner.models import Post


class TextPostPageTests(TestCase):
    def setUp(self):
        admin_group = Group.objects.create(name="Админ")
        self.admin = get_user_model().objects.create_user("admin", password="secret")
        self.admin.groups.add(admin_group)
        for post_id, title in (
            (14, "Calendar text"),
            (15, "Links"),
            (21, "Old renovation title"),
            (22, "Principles"),
        ):
            Post.objects.create(pk=post_id, title=title, content=f"<p>Text {post_id}</p>")

    def test_guest_menu_pages_are_text_only(self):
        for view_name in ("vaishnava_calendar", "nuorodos", "kuryba", "principai"):
            with self.subTest(view_name=view_name):
                response = self.client.get(reverse(f"planner:{view_name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="post-content text-post-content"')
                self.assertNotContains(response, "data-schedule-calendar")
                self.assertNotContains(response, 'id="text-post-editor"')

    def test_old_renovation_url_is_removed(self):
        response = self.client.get("/remonto-darbai/")
        self.assertEqual(response.status_code, 404)

    def test_data_migration_renames_only_the_legacy_heading(self):
        post = Post.objects.get(pk=21)
        post.title = "Šventyklos remonto darbai"
        post.content = "# Šventyklos remonto darbai\n\n<p>Keep this text</p>"
        post.save(update_fields=["title", "content"])
        migration = import_module("planner.migrations.0008_rename_creativity_page")

        migration.rename_creativity_page(apps, None)

        post.refresh_from_db()
        self.assertEqual(post.title, "Kūryba")
        self.assertEqual(post.content, "# Kūryba\n\n<p>Keep this text</p>")

    def test_admin_gets_ckeditor_without_schedule_controls(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("planner:kuryba"))
        self.assertContains(response, 'id="text-post-editor"')
        self.assertContains(response, 'id="id_content"')
        self.assertContains(response, 'window.scheduleEditLockScope = "post\\u002D21"')
        self.assertContains(response, "js/text_post_editor.js")
        self.assertNotContains(response, 'data-marker-controls="main"')

    def test_same_page_is_locked_but_different_page_can_be_edited(self):
        first = Client()
        second = Client()
        first.force_login(self.admin)
        second.force_login(self.admin)
        lock_url = reverse("planner:schedule_edit_lock")

        self.assertEqual(
            first.post(lock_url, {"action": "acquire", "token": "tab-one", "scope": "post-21"}).status_code,
            200,
        )
        self.assertEqual(
            second.post(lock_url, {"action": "acquire", "token": "tab-two", "scope": "post-21"}).status_code,
            409,
        )
        self.assertEqual(
            second.post(lock_url, {"action": "acquire", "token": "links-tab", "scope": "post-15"}).status_code,
            200,
        )

    @patch("planner.views.sync_daily_schedules")
    def test_ajax_save_requires_own_lock_and_does_not_parse_schedule(self, sync_schedule):
        self.client.force_login(self.admin)
        edit_url = reverse("planner:post-edit", args=[21])
        denied = self.client.post(
            edit_url,
            {"content": "<p>New creative text</p>", "edit_lock_token": "page-tab"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(denied.status_code, 409)

        self.client.post(
            reverse("planner:schedule_edit_lock"),
            {"action": "acquire", "token": "page-tab", "scope": "post-21"},
        )
        response = self.client.post(
            edit_url,
            {"content": "<p>New creative text</p>", "edit_lock_token": "page-tab"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "<p>New creative text</p>")
        self.assertEqual(Post.objects.get(pk=21).content, "<p>New creative text</p>")
        sync_schedule.assert_not_called()

    def test_editor_fetches_fresh_text_without_cache(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("planner:post-edit", args=[21]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "<p>Text 21</p>")
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")

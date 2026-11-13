import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from planner.tasks import send_admin_notification
from users.models import UserNotificationSettings


User = get_user_model()


class UserNotificationPreferenceTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="owner",
            email="owner@example.com",
            password="secret",
        )
        self.user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
        )
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_edit_page_can_disable_and_enable_email_notifications(self):
        url = reverse("users:user_update", args=[self.user.pk])

        page = self.client.get(url)
        self.assertContains(
            page,
            "Получать сообщения о регистрациях на обед и фидбеки на почту",
        )
        self.assertContains(page, 'name="receive_email_notifications"', html=False)
        self.assertContains(page, "checked", html=False)

        response = self.client.post(
            url,
            {
                "username": self.user.username,
                "email": self.user.email,
                "groups": [],
            },
        )
        self.assertRedirects(response, reverse("users:user_list"))
        self.assertFalse(
            UserNotificationSettings.objects.get(user=self.user).receive_email_notifications
        )

        response = self.client.post(
            url,
            {
                "username": self.user.username,
                "email": self.user.email,
                "groups": [],
                "receive_email_notifications": "on",
            },
        )
        self.assertRedirects(response, reverse("users:user_list"))
        self.assertTrue(
            UserNotificationSettings.objects.get(user=self.user).receive_email_notifications
        )

    @patch("planner.tasks.send_mail")
    def test_email_is_sent_only_to_users_who_did_not_opt_out(self, send_mail):
        disabled = User.objects.create_user(
            username="disabled",
            email="disabled@example.com",
        )
        legacy = User.objects.create_user(
            username="legacy",
            email="legacy@example.com",
        )
        UserNotificationSettings.objects.create(
            user=disabled,
            receive_email_notifications=False,
        )
        UserNotificationSettings.objects.create(
            user=self.user,
            receive_email_notifications=True,
        )

        with patch.dict(
            os.environ,
            {"BOT_TOKEN": "", "TELEGRAM_CHAT_IDS": ""},
            clear=False,
        ):
            send_admin_notification("Новая регистрация", "Текст")

        recipients = send_mail.call_args.args[3]
        self.assertIn("admin@example.com", recipients)
        self.assertIn("legacy@example.com", recipients)
        self.assertNotIn("disabled@example.com", recipients)

    def test_regular_user_can_edit_only_own_account_without_groups(self):
        original_group = Group.objects.create(name="Админ")
        forbidden_group = Group.objects.create(name="Другая группа")
        self.user.groups.add(original_group)
        another = User.objects.create_user(
            username="another",
            email="another@example.com",
        )
        self.client.logout()
        self.client.force_login(self.user)

        own_url = reverse("users:user_update", args=[self.user.pk])
        response = self.client.get(own_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("groups", response.context["form"].fields)
        response = self.client.post(
            own_url,
            {
                "username": "renamed",
                "email": "new@example.com",
                "groups": [forbidden_group.pk],
                "receive_email_notifications": "on",
            },
        )
        self.assertRedirects(response, reverse("users:user_list"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "renamed")
        self.assertEqual(self.user.email, "new@example.com")
        self.assertEqual(list(self.user.groups.all()), [original_group])

        response = self.client.get(reverse("users:user_update", args=[another.pk]))

        self.assertEqual(response.status_code, 403)

    def test_authenticated_user_sees_all_users_but_only_own_edit_button(self):
        another = User.objects.create_user(
            username="another",
            email="another@example.com",
        )
        self.client.logout()
        self.client.force_login(self.user)

        response = self.client.get(reverse("users:user_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.superuser.username)
        self.assertContains(response, another.username)
        self.assertContains(response, reverse("users:user_update", args=[self.user.pk]))
        self.assertNotContains(response, reverse("users:user_update", args=[another.pk]))
        self.assertNotContains(response, reverse("users:user_delete", args=[another.pk]))
        self.assertNotContains(response, reverse("users:user_add"))

    def test_superuser_can_edit_groups(self):
        group = Group.objects.create(name="Редакторы")
        response = self.client.post(
            reverse("users:user_update", args=[self.user.pk]),
            {
                "username": self.user.username,
                "email": self.user.email,
                "groups": [group.pk],
                "receive_email_notifications": "on",
            },
        )

        self.assertRedirects(response, reverse("users:user_list"))
        self.assertEqual(list(self.user.groups.all()), [group])

from unittest.mock import patch
from types import SimpleNamespace
from datetime import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from calendar_utils.utils import lunch_countdown_context, lunch_registration_deadline
from planner.models import Feedback, LunchParticipant, Post


class HomeFormsTests(TestCase):
    def setUp(self):
        Post.objects.create(pk=12, title="Home", content="")

    def test_home_has_independent_prefixed_forms_and_one_captcha_loader(self):
        response = self.client.get(reverse("planner:new"))

        self.assertContains(response, 'data-schedule-calendar')
        self.assertNotContains(response, 'class="post-content"')
        self.assertNotContains(response, 'id="main-post-editor"')
        self.assertContains(response, 'data-home-form="feedback"')
        self.assertContains(response, 'name="feedback-captcha"')
        self.assertContains(response, 'data-lunch-url=')
        self.assertEqual(response.content.count(b"/recaptcha/api.js?render="), 1)
        if b'data-home-form="lunch"' in response.content:
            self.assertContains(response, 'name="lunch-captcha"')

    def test_deadline_uses_riga_time_and_sunday_to_friday_window(self):
        zone = timezone.get_current_timezone()
        at = lambda day, hour, minute=0: timezone.make_aware(
            datetime(2026, 9, day, hour, minute), zone
        )
        self.assertEqual(lunch_registration_deadline(at(17, 12)), at(18, 22))
        self.assertEqual(lunch_registration_deadline(at(18, 21, 59)), at(18, 22))
        self.assertIsNone(lunch_registration_deadline(at(18, 22)))
        self.assertIsNone(lunch_registration_deadline(at(19, 12)))
        self.assertIsNone(lunch_registration_deadline(at(20, 3, 59)))
        self.assertEqual(lunch_registration_deadline(at(20, 4)), at(25, 22))
        self.assertEqual(lunch_registration_deadline(at(20, 12)), at(25, 22))

    def test_countdown_is_shared_by_home_and_public_content_pages(self):
        Post.objects.create(pk=14, title="Calendar", content="Calendar")
        now = timezone.make_aware(datetime(2026, 9, 18, 21, 30), timezone.get_current_timezone())
        with patch("calendar_utils.utils.timezone.now", return_value=now):
            remaining = lunch_countdown_context()["lunch_registration_remaining_ms"]
            home = self.client.get(reverse("planner:new"))
            calendar = self.client.get(reverse("planner:vaishnava_calendar"))
        self.assertGreater(remaining, 0)
        marker = f'data-registration-remaining-ms="{remaining}"'
        self.assertContains(home, marker)
        self.assertContains(calendar, marker)

    @patch("planner.views.lunch_registration_deadline", return_value=None)
    @patch("calendar_utils.utils.lunch_registration_deadline", return_value=None)
    def test_closed_registration_has_no_home_form_and_rejects_post(self, countdown_deadline, view_deadline):
        page = self.client.get(reverse("planner:new"))
        self.assertContains(page, 'data-registration-remaining-ms="0"')
        self.assertNotContains(page, 'data-home-form="lunch"')
        response = self.client.post(
            reverse("planner:lunch_register"),
            {"lunch-name": "Visitor"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"closed": True})
        self.assertFalse(LunchParticipant.objects.exists())

    @patch("planner.views.queue_admin_notification")
    @patch("django_recaptcha.client.submit")
    def test_feedback_ajax_creates_feedback(self, verify_captcha, queue_notification):
        verify_captcha.return_value = SimpleNamespace(
            is_valid=True, action="feedback", extra_data={"score": 0.9}
        )
        response = self.client.post(
            reverse("planner:feedback"),
            {
                "feedback-name": "Visitor",
                "feedback-email": "visitor@example.com",
                "feedback-text": "A useful suggestion",
                "feedback-captcha": "token",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})
        self.assertEqual(Feedback.objects.get().text, "A useful suggestion")
        self.assertEqual(verify_captcha.call_args.kwargs["recaptcha_response"], "token")
        queue_notification.assert_called_once()

    @patch("planner.views.queue_admin_notification")
    @patch("django_recaptcha.client.submit")
    def test_lunch_ajax_creates_registration(self, verify_captcha, queue_notification):
        verify_captcha.return_value = SimpleNamespace(
            is_valid=True, action="lunch_registration", extra_data={"score": 0.9}
        )
        response = self.client.post(
            reverse("planner:lunch_register"),
            {
                "lunch-name": "Visitor",
                "lunch-email": "visitor@example.com",
                "lunch-portions": "2",
                "lunch-captcha": "token",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})
        self.assertEqual(LunchParticipant.objects.get().portions, 2)
        self.assertEqual(verify_captcha.call_args.kwargs["recaptcha_response"], "token")
        queue_notification.assert_called_once()

    @patch("django_recaptcha.client.submit")
    def test_feedback_validation_errors_do_not_save(self, verify_captcha):
        verify_captcha.return_value = SimpleNamespace(
            is_valid=True, action="feedback", extra_data={"score": 0.9}
        )
        response = self.client.post(
            reverse("planner:feedback"),
            {"feedback-captcha": "token"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json()["errors"])
        self.assertFalse(Feedback.objects.exists())

    @patch("django_recaptcha.client.submit")
    def test_captcha_rejects_wrong_action(self, verify_captcha):
        verify_captcha.return_value = SimpleNamespace(
            is_valid=True, action="lunch_registration", extra_data={"score": 0.9}
        )
        response = self.client.post(
            reverse("planner:feedback"),
            {
                "feedback-name": "Visitor",
                "feedback-email": "visitor@example.com",
                "feedback-text": "A useful suggestion",
                "feedback-captcha": "token",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("captcha", response.json()["errors"])
        self.assertFalse(Feedback.objects.exists())

    @patch("django_recaptcha.client.submit")
    def test_captcha_rejects_low_score(self, verify_captcha):
        verify_captcha.return_value = SimpleNamespace(
            is_valid=True, action="feedback", extra_data={"score": 0.1}
        )
        response = self.client.post(
            reverse("planner:feedback"),
            {
                "feedback-name": "Visitor",
                "feedback-email": "visitor@example.com",
                "feedback-text": "A useful suggestion",
                "feedback-captcha": "token",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("captcha", response.json()["errors"])
        self.assertFalse(Feedback.objects.exists())

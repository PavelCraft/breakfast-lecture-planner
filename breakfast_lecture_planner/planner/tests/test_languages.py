from django.test import TestCase
from django.test import RequestFactory
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation
from django.contrib.auth.models import AnonymousUser
from bs4 import BeautifulSoup


class PublicLanguageTests(TestCase):
    def test_lithuanian_is_default_without_browser_preference(self):
        response = self.client.get(reverse("planner:feedback"))
        self.assertEqual(response.headers["Content-Language"], "lt")

    def test_mobile_language_switcher_preserves_calendar_date(self):
        request = RequestFactory().get("/?calendar_date=2026-09-18")
        request.user = AnonymousUser()
        with translation.override("lt"):
            markup = render_to_string("includes/new_header.html", request=request)
        soup = BeautifulSoup(markup, "html.parser")
        mobile = soup.select_one(".mobile-language-switcher")
        self.assertIsNotNone(mobile)
        self.assertEqual([button.get_text(strip=True) for button in mobile.select("button")], ["LT /", "EN"])
        self.assertEqual(
            [field["value"] for field in mobile.select('input[name="next"]')],
            ["/?calendar_date=2026-09-18"] * 2,
        )

    def test_footer_credit_follows_public_language(self):
        with translation.override("lt"):
            lithuanian = render_to_string("planner/includes/footer_credit.html")
        with translation.override("en"):
            english = render_to_string("planner/includes/footer_credit.html")

        self.assertIn("Sukurta", lithuanian)
        self.assertIn("Developed by", english)
        self.assertIn('href="https://formacode.dev/en"', lithuanian)

    def test_russian_browser_uses_lithuanian_public_site(self):
        response = self.client.get(
            reverse("planner:feedback"), HTTP_ACCEPT_LANGUAGE="ru-RU,ru;q=0.9"
        )

        self.assertEqual(response.headers["Content-Language"], "lt")
        self.assertContains(response, '<html lang="lt">', html=False)

    def test_public_language_switcher_rejects_russian(self):
        self.client.post(
            reverse("set_language"),
            {"language": "ru", "next": reverse("planner:feedback")},
        )

        response = self.client.get(reverse("planner:feedback"))
        self.assertEqual(response.headers["Content-Language"], "lt")

    def test_login_interface_remains_russian(self):
        response = self.client.get(
            reverse("users:login"), HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9"
        )

        self.assertContains(response, '<html lang="ru">', html=False)
        self.assertContains(response, "Имя пользователя")

from django.test import TestCase
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation


class PublicLanguageTests(TestCase):
    def test_footer_credit_follows_public_language(self):
        with translation.override("lt"):
            lithuanian = render_to_string("planner/includes/footer_credit.html")
        with translation.override("en"):
            english = render_to_string("planner/includes/footer_credit.html")

        self.assertIn("Sukurta", lithuanian)
        self.assertIn("Developed by", english)
        self.assertIn('href="https://formacode.dev/en"', lithuanian)

    def test_russian_browser_uses_english_public_site(self):
        response = self.client.get(
            reverse("planner:feedback"), HTTP_ACCEPT_LANGUAGE="ru-RU,ru;q=0.9"
        )

        self.assertEqual(response.headers["Content-Language"], "en")
        self.assertContains(response, '<html lang="en">', html=False)

    def test_public_language_switcher_rejects_russian(self):
        self.client.post(
            reverse("set_language"),
            {"language": "ru", "next": reverse("planner:feedback")},
        )

        response = self.client.get(reverse("planner:feedback"))
        self.assertEqual(response.headers["Content-Language"], "en")

    def test_login_interface_remains_russian(self):
        response = self.client.get(
            reverse("users:login"), HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9"
        )

        self.assertContains(response, '<html lang="ru">', html=False)
        self.assertContains(response, "Имя пользователя")

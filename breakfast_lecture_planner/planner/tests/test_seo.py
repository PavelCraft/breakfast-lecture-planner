from xml.etree import ElementTree

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse
from django.utils import translation

from planner.seo import PUBLIC_PAGES


class SeoTests(SimpleTestCase):
    def test_sitemap_contains_only_guest_menu_pages(self):
        response = self.client.get(reverse("sitemap"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/xml")
        root = ElementTree.fromstring(response.content)
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = [element.text for element in root.findall("s:url/s:loc", namespace)]
        self.assertEqual(
            locations,
            [f"https://malone.guru{reverse(name)}" for name in PUBLIC_PAGES],
        )

    def test_robots_advertises_sitemap(self):
        response = self.client.get(reverse("robots_txt"))
        self.assertContains(response, "Sitemap: https://malone.guru/sitemap.xml")

    def test_public_metadata_follows_language(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        request.resolver_match = resolve("/")
        for language, title in (
            ("lt", "Šri Šri Nitai Gaurasundaros šventykla"),
            ("en", "Sri Sri Nitai Gaurasundara Temple"),
        ):
            with self.subTest(language=language), translation.override(language):
                page = render_to_string("new_base.html", request=request)
                self.assertIn(title, page)
                self.assertIn('<link rel="canonical" href="https://malone.guru/">', page)
                self.assertIn('<meta name="description"', page)
                self.assertNotIn('name="robots" content="noindex', page)

    def test_non_menu_page_is_noindex(self):
        request = RequestFactory().get("/registracija/")
        request.user = AnonymousUser()
        request.resolver_match = resolve("/registracija/")
        page = render_to_string("new_base.html", request=request)
        self.assertIn('<meta name="robots" content="noindex, follow">', page)

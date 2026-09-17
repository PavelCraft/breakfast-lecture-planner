import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from planner.models import HomeScene, Post


class HomeSceneTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="scene-admin", password="test-password")
        self.scene = HomeScene.objects.create(background="home_scene/backgrounds/wave.png")

    def test_images_page_requires_login(self):
        response = self.client.get(reverse("planner:image_list"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.user)
        response = self.client.get(reverse("planner:image_list"))
        self.assertContains(response, "Фон")
        self.assertContains(response, "Объект")

    def test_layout_requires_login(self):
        response = self.client.post(
            reverse("planner:home_scene_layout"),
            data=json.dumps(self.scene.layout),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)

    def test_layout_save_and_invalid_value(self):
        self.client.force_login(self.user)
        layout = self.scene.layout
        layout["watch"]["object_x"] = 42
        url = reverse("planner:home_scene_layout")
        response = self.client.post(url, data=json.dumps(layout), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.scene.refresh_from_db()
        self.assertEqual(self.scene.layout["watch"]["object_x"], 42)

        layout["watch"]["object_x"] = 9999
        response = self.client.post(url, data=json.dumps(layout), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.scene.refresh_from_db()
        self.assertEqual(self.scene.layout["watch"]["object_x"], 42)

    def test_home_page_shows_editor_only_to_logged_in_user(self):
        Post.objects.create(pk=12, title="Home", content="")
        response = self.client.get(reverse("planner:new"))
        self.assertNotContains(response, "Настроить оформление")

        self.client.force_login(self.user)
        response = self.client.get(reverse("planner:new"))
        self.assertContains(response, "Настроить оформление")
        self.assertContains(response, "Лопата")
        self.assertContains(response, "TV")
        self.assertContains(response, "home_scene/backgrounds/wave.png")

        preview = self.client.get(reverse("planner:new") + "?scene_preview=1")
        self.assertNotContains(preview, "Настроить оформление")
        self.assertContains(preview, "home-scene__background")
        self.assertEqual(preview.headers["X-Frame-Options"], "SAMEORIGIN")

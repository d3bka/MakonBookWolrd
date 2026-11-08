from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(MAKONBOOK_WORLD_ENABLED=False)
class WorldAccessGateV5571Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("world_gate_student", password="x")
        self.client.force_login(self.user)

    def test_sidebar_marks_world_as_upcoming(self):
        response = self.client.get(reverse("student_dashboard_root"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-world-upcoming')
        self.assertContains(response, 'UPCOMING')
        self.assertContains(response, 'data-world-upcoming-alert')

    def test_direct_world_get_is_redirected_to_dashboard(self):
        response = self.client.get(reverse("world_home"))
        self.assertRedirects(
            response,
            reverse("student_dashboard_root"),
            fetch_redirect_response=False,
        )

    def test_world_post_api_is_locked(self):
        response = self.client.post(reverse("world_queue_join"), {"subject": "math", "mode": "quick"})
        self.assertEqual(response.status_code, 423)
        self.assertEqual(response.json()["code"], "world_upcoming")


@override_settings(MAKONBOOK_WORLD_ENABLED=True)
class WorldAccessGateEnabledV5571Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("world_gate_enabled", password="x")
        self.client.force_login(self.user)

    def test_sidebar_restores_live_world_link_when_enabled(self):
        response = self.client.get(reverse("student_dashboard_root"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-world-upcoming aria-disabled="true"')
        self.assertContains(response, 'V50.3')

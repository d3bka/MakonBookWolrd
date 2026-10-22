from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class RegistrationRateLimitTests(TestCase):
    """V5580 supersedes public registration: the endpoint is now closed."""

    def test_registration_posts_are_rejected_before_any_user_creation(self):
        User = get_user_model()
        before = User.objects.count()
        for suffix in (1, 2, 3):
            response = self.client.post(
                reverse("register"),
                {
                    "username": f"rateuser{suffix}",
                    "email": f"rate{suffix}@example.com",
                    "password": "short",
                    "confirm_password": "short",
                },
                REMOTE_ADDR="203.0.113.10",
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse("login"))
        self.assertEqual(User.objects.count(), before)

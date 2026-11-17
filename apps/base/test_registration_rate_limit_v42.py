from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse


class RegistrationRateLimitTests(TestCase):
    """V84: sign-up is open again and rate limited per network and per email."""

    def setUp(self):
        cache.clear()

    def test_repeated_sign_ups_for_one_email_are_limited(self):
        codes = []
        for _ in range(6):
            response = self.client.post(reverse("register"), {
                "first_name": "Rate", "last_name": "Limit", "email": "rate@example.com",
                "password": "Makon-Strong-2026", "password2": "Makon-Strong-2026", "agree": "1",
            }, REMOTE_ADDR="203.0.113.10")
            codes.append(response.status_code)
        self.assertIn(429, codes)
        self.assertLessEqual(len(mail.outbox), 4)
        self.assertFalse(get_user_model().objects.filter(email="rate@example.com").exists())

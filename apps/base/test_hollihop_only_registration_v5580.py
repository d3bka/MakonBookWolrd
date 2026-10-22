from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.base.adapters import HollihopOnlyAccountAdapter, HollihopOnlySocialAccountAdapter


class HollihopOnlyRegistrationV5580Tests(TestCase):
    def test_legacy_register_get_redirects_without_rendering_signup(self):
        response = self.client.get(reverse("register"), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))

    def test_legacy_register_post_cannot_create_user(self):
        User = get_user_model()
        before = User.objects.count()
        response = self.client.post(
            reverse("register"),
            {
                "username": "external-student",
                "email": "external@example.com",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))
        self.assertEqual(User.objects.count(), before)
        self.assertFalse(User.objects.filter(username="external-student").exists())

    def test_allauth_account_signup_is_closed(self):
        request = RequestFactory().get("/accounts/signup/")
        self.assertFalse(HollihopOnlyAccountAdapter().is_open_for_signup(request))

    def test_allauth_social_signup_is_closed(self):
        request = RequestFactory().get("/accounts/google/login/")
        self.assertFalse(HollihopOnlySocialAccountAdapter().is_open_for_signup(request, object()))

    def test_login_page_has_no_public_create_account_link(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Create account")

    def test_sitemap_does_not_advertise_register(self):
        response = self.client.get("/sitemap.xml")
        self.assertNotContains(response, "/register/")

"""V5580 closed public sign-up; V84 opened MakonBook's own email sign-up again (see
test_registration_v84.py). allauth's generic sign-up and Google sign-up stay closed."""
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.base.adapters import HollihopOnlyAccountAdapter, HollihopOnlySocialAccountAdapter


class HollihopOnlyRegistrationV5580Tests(TestCase):
    def test_register_page_is_the_v84_email_sign_up(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Send the code")

    def test_allauth_account_signup_is_closed(self):
        request = RequestFactory().get("/accounts/signup/")
        self.assertFalse(HollihopOnlyAccountAdapter().is_open_for_signup(request))

    def test_allauth_social_signup_is_closed(self):
        request = RequestFactory().get("/accounts/google/login/")
        self.assertFalse(HollihopOnlySocialAccountAdapter().is_open_for_signup(request, object()))

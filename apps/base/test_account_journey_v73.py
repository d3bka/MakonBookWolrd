"""V73 A-to-Z: sign-in, sign-out, temporary password and activation links at the view level."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.base.models import EmailVerification


class SignInTests(TestCase):
    def setUp(self):
        cache.clear()  # the auth rate limiter lives in the cache
        self.user = User.objects.create_user("acc_kid", email="kid@example.com", password="Correct-Horse-91")

    def login(self, credential, password):
        return self.client.post(reverse("login"), {"username": credential, "password": password}, follow=True)

    def test_username_and_email_both_sign_in(self):
        response = self.login("acc_kid", "Correct-Horse-91")
        self.assertTrue(response.context["user"].is_authenticated)
        self.client.logout()
        response = self.login("KID@example.com", "Correct-Horse-91")
        self.assertTrue(response.context["user"].is_authenticated)

    def test_wrong_password_is_refused(self):
        response = self.login("acc_kid", "nope")
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertContains(response, "is incorrect")

    def test_deactivated_account_is_told_why_only_with_the_right_password(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        response = self.login("acc_kid", "Correct-Horse-91")
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertContains(response, "not active")
        # wrong password: no hint that the account exists
        response = self.login("acc_kid", "nope")
        self.assertContains(response, "is incorrect")
        self.assertNotContains(response, "not active")

    def test_unknown_user_gets_the_generic_message(self):
        self.assertContains(self.login("ghost", "whatever"), "is incorrect")

    def test_logout_ends_the_session(self):
        self.client.force_login(self.user)
        self.client.get(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)


class TemporaryPasswordTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("acc_temp", password="Temp-12345")
        self.user.profile.must_change_password = True
        self.user.profile.save()
        self.client.force_login(self.user)

    def test_every_page_sends_the_user_to_change_the_password_first(self):
        response = self.client.get(reverse("student_dashboard_root"))
        self.assertRedirects(response, reverse("change_temporary_password"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("change_temporary_password")).status_code, 200)

    def test_weak_password_is_rejected_and_strong_one_unlocks_the_account(self):
        url = reverse("change_temporary_password")
        response = self.client.post(url, {"new_password1": "123", "new_password2": "123"})
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.must_change_password)

        response = self.client.post(url, {"new_password1": "Blue-Panda-2026!", "new_password2": "Blue-Panda-2026!"})
        self.assertRedirects(response, reverse("student_dashboard_root"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.must_change_password)
        self.assertTrue(self.user.check_password("Blue-Panda-2026!"))
        # still signed in after the change, and the dashboard opens now
        self.assertEqual(self.client.get(reverse("student_dashboard_root")).status_code, 200)

    def test_page_is_not_reachable_once_the_password_was_changed(self):
        self.user.profile.must_change_password = False
        self.user.profile.save()
        response = self.client.get(reverse("change_temporary_password"))
        self.assertRedirects(response, reverse("student_dashboard_root"), fetch_redirect_response=False)


class ActivationLinkTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("acc_new", password="x", is_active=False)

    def test_link_activates_once(self):
        link = EmailVerification.objects.create(user=self.user)
        self.client.get(reverse("activate", args=[link.token]))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        response = self.client.get(reverse("activate", args=[link.token]), follow=True)
        self.assertContains(response, "Invalid or expired")

    def test_expired_link_does_nothing(self):
        link = EmailVerification.objects.create(user=self.user, expires_at=timezone.now() - timedelta(minutes=1))
        response = self.client.get(reverse("activate", args=[link.token]), follow=True)
        self.assertContains(response, "Invalid or expired")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

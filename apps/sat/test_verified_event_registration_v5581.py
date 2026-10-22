import re
from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.sat.event_registration import find_makonbook_student, find_makonbook_student_by_username
from apps.sat.models import EventRegistration, GlobalEvent, Test


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@makonbook.local",
    MAKONBOOK_GUEST_MODE_ENABLED=False,
)
class VerifiedEventRegistrationV5581Tests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.test_obj = Test.objects.create(name="V5581 MOCK SOURCE")
        self.event = GlobalEvent.objects.create(
            title="V5581 Mock Exam",
            slug="v5581-mock",
            test=self.test_obj,
            is_public=True,
            status="scheduled",
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(hours=6),
            registration_enabled=True,
            show_on_landing=True,
            branch="NOVZA",
            capacity=2,
            registration_opens_at=now - timedelta(hours=1),
            registration_closes_at=now + timedelta(hours=1),
            verification_minutes=10,
        )

    def _student(self, username="hstu_88001", email="islom@example.com", password="MockPass-8821"):
        user = User.objects.create_user(
            username=username,
            first_name="Islom",
            last_name="Baxtiyorov",
            email=email,
            password=password,
        )
        user.profile.hollihop_client_id = 88001
        user.profile.phone_number = "+998901112233"
        user.profile.save(update_fields=["hollihop_client_id", "phone_number", "updated_at"])
        return user

    def _last_code(self):
        self.assertTrue(mail.outbox)
        match = re.search(r"\n\n(\d{6})\n\n", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_external_registration_hashes_code_and_confirms(self):
        response = self.client.post(
            reverse("event_registration_external", kwargs={"slug": self.event.slug}),
            {
                "full_name": "External Student",
                "phone": "+998901234567",
                "email": "external@example.com",
                "telegram": "@external_user",
            },
        )
        self.assertEqual(response.status_code, 302)
        registration = EventRegistration.objects.get(email="external@example.com")
        self.assertEqual(registration.status, EventRegistration.STATUS_PENDING)
        self.assertTrue(registration.verification_code_hash)
        self.assertNotRegex(registration.verification_code_hash, r"^\d{6}$")
        self.assertEqual(len(mail.outbox), 1)

        response = self.client.post(
            reverse("event_registration_verify", kwargs={"token": registration.registration_token}),
            {"code": self._last_code()},
        )
        self.assertEqual(response.status_code, 302)
        registration.refresh_from_db()
        self.assertEqual(registration.status, EventRegistration.STATUS_CONFIRMED)
        self.assertIsNotNone(registration.guest_id)
        self.assertEqual(registration.verification_code_hash, "")

    def test_public_student_flow_requires_username_then_password_then_otp(self):
        user = self._student()
        url = reverse("event_registration_student", kwargs={"slug": self.event.slug})

        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)
        self.assertContains(first, 'name="username"')
        self.assertNotContains(first, 'name="password"')

        # Email is deliberately not an account-discovery key in this public flow.
        by_email = self.client.post(url, {"action": "lookup", "username": user.email})
        self.assertEqual(by_email.status_code, 200)
        self.assertContains(by_email, "Username or password is incorrect")
        self.assertNotContains(by_email, 'name="password"')

        lookup = self.client.post(url, {"action": "lookup", "username": user.username})
        self.assertEqual(lookup.status_code, 200)
        self.assertContains(lookup, 'name="password"')
        self.assertContains(lookup, f'value="{user.pk}"')
        self.assertEqual(EventRegistration.objects.filter(user=user).count(), 0)

        wrong = self.client.post(
            url,
            {
                "action": "password",
                "username": user.username,
                "student_user_id": str(user.pk),
                "password": "wrong-password",
            },
        )
        self.assertEqual(wrong.status_code, 200)
        self.assertContains(wrong, "Username or password is incorrect")
        self.assertEqual(EventRegistration.objects.filter(user=user).count(), 0)

        sent = self.client.post(
            url,
            {
                "action": "password",
                "username": user.username,
                "student_user_id": str(user.pk),
                "password": "MockPass-8821",
            },
        )
        self.assertEqual(sent.status_code, 302)
        registration = EventRegistration.objects.get(user=user)
        self.assertEqual(registration.status, EventRegistration.STATUS_PENDING)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Your verification code", mail.outbox[0].body)
        self.assertNotIn("_auth_user_id", self.client.session)

        verified = self.client.post(
            reverse("event_registration_verify", kwargs={"token": registration.registration_token}),
            {"code": self._last_code()},
        )
        self.assertEqual(verified.status_code, 302)
        registration.refresh_from_db()
        self.assertEqual(registration.status, EventRegistration.STATUS_CONFIRMED)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_authenticated_student_registers_directly_without_username_or_password(self):
        user = self._student(username="hstu_workspace", email="workspace@example.com")
        self.client.force_login(user)
        url = reverse("event_registration_student", kwargs={"slug": self.event.slug})

        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Your MakonBook account")
        self.assertNotContains(page, 'name="username"')
        self.assertNotContains(page, 'name="password"')

        sent = self.client.post(url, {"action": "send"})
        self.assertEqual(sent.status_code, 302)
        registration = EventRegistration.objects.get(user=user)
        self.assertEqual(registration.status, EventRegistration.STATUS_PENDING)
        self.assertEqual(len(mail.outbox), 1)

        verified = self.client.post(
            reverse("event_registration_verify", kwargs={"token": registration.registration_token}),
            {"code": self._last_code()},
        )
        self.assertEqual(verified.status_code, 302)
        registration.refresh_from_db()
        self.assertEqual(registration.status, EventRegistration.STATUS_CONFIRMED)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_pending_verification_holds_capacity(self):
        self.event.capacity = 1
        self.event.save(update_fields=["capacity"])
        self.client.post(
            reverse("event_registration_external", kwargs={"slug": self.event.slug}),
            {"full_name": "Seat One", "phone": "+998901111111", "email": "one@example.com"},
        )
        response = self.client.post(
            reverse("event_registration_external", kwargs={"slug": self.event.slug}),
            {"full_name": "Seat Two", "phone": "+998902222222", "email": "two@example.com"},
            follow=True,
        )
        self.assertEqual(EventRegistration.objects.count(), 1)
        self.assertContains(response, "Registration is full", status_code=200)

    def test_makonbook_student_lookup_does_not_require_hollihop_link(self):
        user = User.objects.create_user(
            username="mockstudent",
            email="mockstudent@example.com",
            password="StrongPass123!",
        )
        # Legacy/current MakonBook student accounts remain eligible even before
        # a Hollihop foreign key has been attached. Public sign-up itself is
        # disabled elsewhere, so event registration should verify the account
        # rather than its provisioning source.
        self.assertEqual(find_makonbook_student("mockstudent").pk, user.pk)
        self.assertEqual(find_makonbook_student_by_username("mockstudent").pk, user.pk)

    def test_authenticated_student_without_hollihop_link_can_send_otp_from_profile_email(self):
        user = User.objects.create_user(
            username="legacy_student",
            first_name="Legacy",
            last_name="Student",
            email="legacy@example.com",
            password="StrongPass123!",
        )
        self.assertIsNone(user.profile.hollihop_client_id)
        self.client.force_login(user)
        response = self.client.post(
            reverse("event_registration_student", kwargs={"slug": self.event.slug}),
            {"action": "send"},
        )
        self.assertEqual(response.status_code, 302)
        registration = EventRegistration.objects.get(user=user)
        self.assertEqual(registration.email, "legacy@example.com")
        self.assertEqual(registration.status, EventRegistration.STATUS_PENDING)
        self.assertEqual(len(mail.outbox), 1)

    def test_authenticated_workspace_ajax_stays_inline_for_otp_and_confirmation(self):
        user = self._student(username="hstu_inline", email="inline@example.com")
        self.client.force_login(user)
        register_url = reverse("event_registration_student", kwargs={"slug": self.event.slug})

        sent = self.client.post(
            register_url,
            {"action": "send"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(sent.status_code, 200)
        payload = sent.json()
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["confirmed"])
        self.assertEqual(payload["masked_email"], "in****@example.com")
        self.assertTrue(payload["verify_url"])
        self.assertTrue(payload["resend_url"])
        registration = EventRegistration.objects.get(user=user)
        self.assertEqual(registration.status, EventRegistration.STATUS_PENDING)
        self.assertEqual(len(mail.outbox), 1)

        wrong = self.client.post(
            payload["verify_url"],
            {"code": "000000"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(wrong.status_code, 400)
        self.assertFalse(wrong.json()["ok"])

        verified = self.client.post(
            payload["verify_url"],
            {"code": self._last_code()},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(verified.status_code, 200)
        verified_payload = verified.json()
        self.assertTrue(verified_payload["ok"])
        self.assertTrue(verified_payload["confirmed"])
        self.assertTrue(verified_payload["confirmation_url"])
        registration.refresh_from_db()
        self.assertEqual(registration.status, EventRegistration.STATUS_CONFIRMED)

    def test_legacy_guest_entry_is_closed(self):
        response = self.client.get(reverse("guest_entry"))
        self.assertRedirects(response, reverse("home"))

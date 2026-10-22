import re
from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.sat.event_registration import (
    event_confirmed_count,
    event_pending_hold_count,
    seats_left,
)
from apps.sat.models import EventRegistration, GlobalEvent, Test


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@makonbook.local",
    MAKONBOOK_GUEST_MODE_ENABLED=False,
)
class MockRegistrationV5589Tests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.test_obj = Test.objects.create(name="V5589 MOCK SOURCE")
        self.event = GlobalEvent.objects.create(
            title="V5589 Mock Exam",
            slug="v5589-mock",
            test=self.test_obj,
            is_public=True,
            status="scheduled",
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(hours=6),
            registration_enabled=True,
            show_on_landing=True,
            branch="NOVZA",
            capacity=50,
            registration_opens_at=now - timedelta(hours=1),
            registration_closes_at=now + timedelta(hours=1),
            verification_minutes=10,
        )

    def _verification_code(self):
        self.assertTrue(mail.outbox)
        match = re.search(r"\n\n(\d{6})\n\n", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_confirmation_email_contains_registration_id_and_checklist(self):
        self.client.post(
            reverse("event_registration_external", kwargs={"slug": self.event.slug}),
            {
                "full_name": "External Student",
                "phone": "+998901234567",
                "email": "external@example.com",
                "telegram": "@external_user",
            },
        )
        registration = EventRegistration.objects.get(email="external@example.com")
        code = self._verification_code()
        self.assertEqual(len(mail.outbox), 1)

        response = self.client.post(
            reverse("event_registration_verify", kwargs={"token": registration.registration_token}),
            {"code": code},
        )
        self.assertEqual(response.status_code, 302)
        registration.refresh_from_db()
        self.assertEqual(registration.status, EventRegistration.STATUS_CONFIRMED)
        self.assertEqual(len(mail.outbox), 2)

        confirmation = mail.outbox[-1]
        self.assertIn("registration confirmed", confirmation.subject.lower())
        self.assertIn(registration.registration_id, confirmation.body)
        self.assertIn("CHECKLIST", confirmation.body)
        self.assertIn("Arrive at least 15 minutes", confirmation.body)
        self.assertIn("NOVZA", confirmation.body)

    def test_workspace_ajax_returns_registration_id_and_email_delivery_status(self):
        user = User.objects.create_user(
            username="v5589student",
            first_name="Islom",
            last_name="Baxtiyorov",
            email="v5589@example.com",
            password="StrongPass123!",
        )
        self.client.force_login(user)
        send = self.client.post(
            reverse("event_registration_student", kwargs={"slug": self.event.slug}),
            {"action": "send"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(send.status_code, 200)
        registration = EventRegistration.objects.get(user=user)
        code = self._verification_code()

        verified = self.client.post(
            send.json()["verify_url"],
            {"code": code},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(verified.status_code, 200)
        payload = verified.json()
        self.assertTrue(payload["confirmed"])
        self.assertEqual(payload["registration_id"], registration.registration_id)
        self.assertTrue(payload["confirmation_email_sent"])
        self.assertEqual(payload["confirmed_count"], 1)
        self.assertEqual(payload["pending_hold_count"], 0)
        self.assertEqual(payload["seats_left"], 49)
        self.assertEqual(len(mail.outbox), 2)

    def test_pending_verification_explains_reserved_seat_math(self):
        EventRegistration.objects.create(
            event=self.event,
            participant_type=EventRegistration.TYPE_EXTERNAL,
            full_name="Confirmed",
            email="confirmed@example.com",
            phone="+998901111111",
            status=EventRegistration.STATUS_CONFIRMED,
            verified_at=timezone.now(),
        )
        EventRegistration.objects.create(
            event=self.event,
            participant_type=EventRegistration.TYPE_EXTERNAL,
            full_name="Pending",
            email="pending@example.com",
            phone="+998902222222",
            status=EventRegistration.STATUS_PENDING,
            verification_expires_at=timezone.now() + timedelta(minutes=10),
        )
        self.assertEqual(event_confirmed_count(self.event), 1)
        self.assertEqual(event_pending_hold_count(self.event), 1)
        self.assertEqual(seats_left(self.event), 48)

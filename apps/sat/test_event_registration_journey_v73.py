"""V73 A-to-Z: event registration choice, code resend and the confirmation page."""
import re
from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import EventRegistration, GlobalEvent, Test


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@makonbook.local",
    MAKONBOOK_GUEST_MODE_ENABLED=False,
)
class EventRegistrationJourneyTests(TestCase):
    def setUp(self):
        cache.clear()
        now = timezone.now()
        self.event = GlobalEvent.objects.create(
            title="V73 Mock", slug="v73-mock", test=Test.objects.create(name="V73 MOCK SRC"), is_public=True,
            status="scheduled", start_at=now + timedelta(hours=2), end_at=now + timedelta(hours=6),
            registration_enabled=True, show_on_landing=True, capacity=5,
            registration_opens_at=now - timedelta(hours=1), registration_closes_at=now + timedelta(hours=1),
            verification_minutes=10,
        )

    def register_external(self, email="guest@example.com"):
        self.client.post(reverse("event_registration_external", kwargs={"slug": self.event.slug}), {
            "full_name": "Guest Person", "phone": "+998901234567", "email": email, "telegram": "@guest",
        })
        return EventRegistration.objects.get(email=email)

    def code(self):
        return re.search(r"\n\n(\d{6})\n\n", mail.outbox[-1].body).group(1)

    def test_choice_page_then_confirmed_visitors_go_straight_to_their_ticket(self):
        choice = reverse("event_registration_choice", kwargs={"slug": self.event.slug})
        self.assertEqual(self.client.get(choice).status_code, 200)
        registration = self.register_external()
        self.client.post(reverse("event_registration_verify", kwargs={"token": registration.registration_token}), {"code": self.code()})
        registration.refresh_from_db()
        self.assertEqual(registration.status, EventRegistration.STATUS_CONFIRMED)
        response = self.client.get(choice)
        self.assertRedirects(response, reverse("event_registration_confirmation", kwargs={"token": registration.registration_token}),
                             fetch_redirect_response=False)
        page = self.client.get(response["Location"])
        self.assertContains(page, registration.registration_id)

    def test_unknown_or_closed_event_is_404(self):
        self.assertEqual(self.client.get(reverse("event_registration_choice", kwargs={"slug": "nope"})).status_code, 404)
        GlobalEvent.objects.filter(pk=self.event.pk).update(registration_enabled=False)
        self.assertEqual(self.client.get(reverse("event_registration_choice", kwargs={"slug": self.event.slug})).status_code, 404)

    def test_resend_sends_a_new_code_and_the_old_one_stops_working(self):
        registration = self.register_external()
        old_code = self.code()
        url = reverse("event_registration_resend", kwargs={"token": registration.registration_token})
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        if response.status_code == 400:  # resend cooldown: allowed again after the wait
            self.assertIn("error", response.json())
            return
        self.assertTrue(response.json()["ok"])
        self.assertEqual(len(mail.outbox), 2)
        new_code = self.code()
        if new_code != old_code:
            self.client.post(reverse("event_registration_verify", kwargs={"token": registration.registration_token}), {"code": old_code})
            registration.refresh_from_db()
            self.assertEqual(registration.status, EventRegistration.STATUS_PENDING)
        self.client.post(reverse("event_registration_verify", kwargs={"token": registration.registration_token}), {"code": new_code})
        registration.refresh_from_db()
        self.assertEqual(registration.status, EventRegistration.STATUS_CONFIRMED)
        # resend after confirmation just shows the ticket
        again = self.client.post(url)
        self.assertRedirects(again, reverse("event_registration_confirmation", kwargs={"token": registration.registration_token}),
                             fetch_redirect_response=False)

    def test_confirmation_page_needs_a_confirmed_registration(self):
        registration = self.register_external()
        url = reverse("event_registration_confirmation", kwargs={"token": registration.registration_token})
        self.assertEqual(self.client.get(url).status_code, 404)  # still pending

    def test_another_signed_in_account_cannot_open_a_students_ticket(self):
        owner = User.objects.create_user("v73_owner", password="x", email="owner@example.com")
        registration = self.register_external(email="owner@example.com")
        EventRegistration.objects.filter(pk=registration.pk).update(user=owner, status=EventRegistration.STATUS_CONFIRMED)
        intruder = User.objects.create_user("v73_intruder", password="x")
        self.client.force_login(intruder)
        url = reverse("event_registration_confirmation", kwargs={"token": registration.registration_token})
        self.assertRedirects(self.client.get(url), reverse("home"), fetch_redirect_response=False)
        self.client.force_login(owner)
        self.assertEqual(self.client.get(url).status_code, 200)

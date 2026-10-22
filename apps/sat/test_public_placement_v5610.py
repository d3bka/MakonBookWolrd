from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.sat.guest_views import finalize_attempt
from apps.sat.models import (
    English_Question,
    GlobalEvent,
    GlobalEventAttempt,
    PlacementTelegramNotification,
    PublicPlacementLead,
    Test,
)


@override_settings(MAKONBOOK_GUEST_MODE_ENABLED=False)
class PublicPlacementV5610Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.test = Test.objects.create(name="PUBLIC LEVEL TEST", is_available=True)
        English_Question.objects.create(
            test=self.test,
            module="module_1",
            number=1,
            question="Public placement sample",
            answer="A",
        )
        now = timezone.now()
        self.event = GlobalEvent.objects.create(
            title="English Level Check",
            slug="english-level-check-v5610",
            event_type=GlobalEvent.TYPE_PLACEMENT,
            test=self.test,
            is_public=True,
            status="live",
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=2),
            english_duration_minutes=30,
            math_duration_minutes=30,
            registration_enabled=False,
        )

    def test_public_level_page_lists_live_placement_without_login(self):
        regular_event = GlobalEvent.objects.create(
            title="Normal Mock",
            slug="normal-mock-v5610",
            event_type=GlobalEvent.TYPE_EVENT,
            test=self.test,
            is_public=True,
            status="live",
            start_at=timezone.now() - timedelta(minutes=5),
            end_at=timezone.now() + timedelta(hours=2),
        )
        response = self.client.get(reverse("public_placement_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.title)
        self.assertContains(response, "Check my level")
        self.assertNotContains(response, regular_event.title)

    def test_public_start_captures_identity_creates_attempt_and_queues_telegram(self):
        response = self.client.post(
            reverse("public_placement_start", args=[self.event.slug]),
            {
                "first_name": "Aziz",
                "last_name": "Karimov",
                "phone_number": "90 123 45 67",
                "consent_to_contact": "1",
            },
        )
        lead = PublicPlacementLead.objects.select_related("attempt", "guest").get()
        self.assertEqual(lead.phone_number, "+998901234567")
        self.assertEqual(lead.full_name, "Aziz Karimov")
        self.assertIsNotNone(lead.attempt_id)
        self.assertEqual(lead.attempt.event_id, self.event.id)
        self.assertEqual(lead.attempt.total_questions, 1)
        self.assertEqual(response.status_code, 302)
        self.assertIn(str(lead.attempt.guest_token), response.url)
        self.assertTrue(self.client.session.get("public_placement_guest"))
        self.assertTrue(
            PlacementTelegramNotification.objects.filter(
                lead=lead,
                kind=PlacementTelegramNotification.KIND_STARTED,
                status=PlacementTelegramNotification.STATUS_PENDING,
            ).exists()
        )

    def test_public_session_can_open_guest_runner_while_legacy_guest_mode_is_disabled(self):
        self.client.post(
            reverse("public_placement_start", args=[self.event.slug]),
            {
                "first_name": "Laylo",
                "last_name": "Aliyeva",
                "phone_number": "+998 91 111 22 33",
                "consent_to_contact": "1",
            },
        )
        lead = PublicPlacementLead.objects.select_related("attempt").get()
        response = self.client.get(reverse("global_event_attempt_root", args=[lead.attempt.guest_token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.title)
        self.assertContains(response, f'href="{reverse("public_placement_list")}"')

    def test_invalid_phone_does_not_create_public_lead(self):
        response = self.client.post(
            reverse("public_placement_start", args=[self.event.slug]),
            {
                "first_name": "Ali",
                "last_name": "Valiyev",
                "phone_number": "123",
                "consent_to_contact": "1",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "valid Uzbekistan phone number", status_code=400)
        self.assertFalse(PublicPlacementLead.objects.exists())
        self.assertFalse(GlobalEventAttempt.objects.exists())

    def test_finalizing_public_placement_queues_completed_notification(self):
        self.client.post(
            reverse("public_placement_start", args=[self.event.slug]),
            {
                "first_name": "Madina",
                "last_name": "Hasanova",
                "phone_number": "+998901111111",
                "consent_to_contact": "1",
            },
        )
        lead = PublicPlacementLead.objects.select_related("attempt").get()
        finalize_attempt(lead.attempt)
        lead.refresh_from_db()
        self.assertIsNotNone(lead.completed_at)
        self.assertTrue(
            PlacementTelegramNotification.objects.filter(
                lead=lead,
                kind=PlacementTelegramNotification.KIND_COMPLETED,
            ).exists()
        )

    def test_landing_exposes_check_your_level_cta(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Check your level")
        self.assertContains(response, reverse("public_placement_list"))

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.sat.guest_views import finalize_attempt
from apps.sat.models import (
    English_Question,
    GlobalEvent,
    PlacementTelegramNotification,
    PublicPlacementLead,
    Test,
)
from apps.telegram_bot.placement_notifications import _format_message, _notification_snapshot


@override_settings(MAKONBOOK_GUEST_MODE_ENABLED=False, SITE_URL="https://makonbook.uz")
class PublicPlacementV5612Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.test = Test.objects.create(name="LEVEL CHECK V5612", is_available=True)
        English_Question.objects.create(
            test=self.test,
            module="module_1",
            number=1,
            question="Placement sample",
            answer="A",
        )
        now = timezone.now()
        self.event = GlobalEvent.objects.create(
            title="English Level Check",
            slug="english-level-check-v5612",
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

    def start_public_attempt(self):
        response = self.client.post(
            reverse("public_placement_start", args=[self.event.slug]),
            {
                "first_name": "Laylo",
                "last_name": "Aliyeva",
                "phone_number": "+998 91 111 22 33",
                "consent_to_contact": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        return PublicPlacementLead.objects.select_related("attempt").get()

    def test_level_check_list_exposes_question_time_and_module_metadata(self):
        response = self.client.get(reverse("public_placement_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 level check available now")
        self.assertContains(response, "1</strong><span>Questions")
        self.assertContains(response, "≈ 30</strong><span>Minutes")
        self.assertContains(response, "One test. Three simple steps.")

    def test_public_runner_has_level_check_branding_without_touching_standard_mode(self):
        lead = self.start_public_attempt()
        response = self.client.get(reverse("global_event_attempt_root", args=[lead.attempt.guest_token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pp-test-runner")
        self.assertContains(response, "public-placement-runner-v5612.css")
        # The test screen's header shows only the section, as for every test.
        self.assertNotContains(response, "pp-runner-badge")

    def test_completed_public_placement_uses_dedicated_result_experience(self):
        lead = self.start_public_attempt()
        finalize_attempt(lead.attempt)
        response = self.client.get(reverse("global_event_result_root", args=[lead.attempt.guest_token]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "sat/public_placement/result.html")
        self.assertContains(response, "Laylo, your current level is ready.")
        self.assertContains(response, "Foundation")
        self.assertContains(response, "Your result is already recorded.")
        self.assertContains(response, "Share result")

    def test_telegram_placement_message_contains_direct_admin_lead_link(self):
        lead = self.start_public_attempt()
        notice = PlacementTelegramNotification.objects.get(
            lead=lead,
            kind=PlacementTelegramNotification.KIND_STARTED,
        )
        payload = _notification_snapshot(notice.pk)
        message = _format_message(payload)
        self.assertIn("Lead #", message)
        self.assertIn("Open lead in MakonBook", message)
        self.assertIn("https://makonbook.uz/admin/sat/publicplacementlead/", message)


    def test_hidden_score_public_result_does_not_leak_raw_correct_count(self):
        self.event.show_score_immediately = False
        self.event.save(update_fields=["show_score_immediately"])
        lead = self.start_public_attempt()
        finalize_attempt(lead.attempt)
        response = self.client.get(reverse("global_event_result_root", args=[lead.attempt.guest_token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Result recorded")
        self.assertContains(response, "Hidden")
        self.assertNotContains(response, "0 / 1")

    def test_v5612_frontend_assets_keep_phone_formatting_and_share_fallback(self):
        js = (Path(settings.BASE_DIR) / "static/assets/js/public-placement-v5612.js").read_text(encoding="utf-8")
        css = (Path(settings.BASE_DIR) / "static/assets/css/public-placement-v5612.css").read_text(encoding="utf-8")
        self.assertIn("formatUzbekPhone", js)
        self.assertIn("navigator.share", js)
        self.assertIn("navigator.clipboard", js)
        self.assertIn("pp12-score-ring", css)
        self.assertIn("prefers-reduced-motion", css)

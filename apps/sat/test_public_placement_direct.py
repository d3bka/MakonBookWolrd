from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.sat.guest_views import attempt_sequence, calculate_attempt_breakdown, get_guest_current_step
from apps.sat.models import (
    English_Question,
    GlobalEvent,
    GlobalEventAnswer,
    GlobalEventAttempt,
    Math_Question,
    PublicPlacementLead,
    Test,
)


@override_settings(MAKONBOOK_GUEST_MODE_ENABLED=False)
class DirectPlacementLinkTests(TestCase):
    """/check-level/english/ and /check-level/math/: one section, no name or phone."""

    def setUp(self):
        cache.clear()
        self.test = Test.objects.create(name="LEVEL CHECK DIRECT", is_available=True)
        self.english = [
            English_Question.objects.create(test=self.test, module="module_1", number=n, question=f"E{n}", a="a", b="b", c="c", d="d", answer="A")
            for n in (1, 2)
        ]
        self.math = [
            Math_Question.objects.create(test=self.test, module="module_1", number=n, question=f"M{n}", a="1", b="2", c="3", d="4", answer="B")
            for n in (1, 2, 3)
        ]
        now = timezone.now()
        self.event = GlobalEvent.objects.create(
            title="SAT Level Check",
            slug="sat-level-check",
            event_type=GlobalEvent.TYPE_PLACEMENT,
            test=self.test,
            is_public=True,
            status="live",
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(days=30),
            english_duration_minutes=30,
            math_duration_minutes=35,
            registration_enabled=False,
        )

    def start(self, section):
        response = self.client.post(reverse(f"public_placement_direct_{section}"))
        self.assertEqual(response.status_code, 302)
        return GlobalEventAttempt.objects.order_by("-id").first()

    def test_the_start_page_asks_for_nothing(self):
        response = self.client.get(reverse("public_placement_direct_english"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reading and Writing")
        self.assertContains(response, "Start the English level check")
        self.assertNotContains(response, 'name="phone_number"')
        self.assertNotContains(response, 'name="first_name"')
        self.assertContains(response, "2</strong>")  # questions in the English section only

    def test_english_link_runs_only_english_without_a_lead(self):
        attempt = self.start("english")
        self.assertEqual(attempt.run_mode, GlobalEventAttempt.RUN_ENGLISH)
        self.assertEqual(attempt.total_questions, 2)
        self.assertEqual(attempt_sequence(attempt), [("english", "m1")])
        self.assertEqual(get_guest_current_step(attempt), ("english", "m1"))
        self.assertFalse(PublicPlacementLead.objects.exists())
        page = self.client.get(reverse("global_event_attempt_root", args=[attempt.guest_token]))
        self.assertEqual(page.status_code, 200)
        self.assertTemplateUsed(page, "test/shared/attempt_eng.html")

    def test_math_link_runs_only_math(self):
        attempt = self.start("math")
        self.assertEqual(attempt.run_mode, GlobalEventAttempt.RUN_MATH)
        self.assertEqual(attempt.total_questions, 3)
        self.assertEqual(attempt_sequence(attempt), [("math", "m1")])

    def test_result_shows_the_level_and_the_section_score_out_of_800(self):
        attempt = self.start("english")
        for question in self.english:
            GlobalEventAnswer.objects.create(attempt=attempt, section="english", module="m1", question_id=question.id, selected_answer="A")
        # An answer for the other section never counts.
        GlobalEventAnswer.objects.create(attempt=attempt, section="math", module="m1", question_id=self.math[0].id, selected_answer="B")
        attempt.completed_modules = ["english:m1"]
        attempt.save(update_fields=["completed_modules"])

        breakdown = calculate_attempt_breakdown(attempt)
        self.assertEqual(breakdown["total_raw"], 2)
        self.assertEqual(breakdown["math_raw"], 0)
        self.assertEqual(breakdown["placement_total_questions"], 2)
        self.assertEqual(breakdown["placement"]["level_name"], "Advanced")
        self.assertIsNotNone(breakdown["ebrw_score"])
        self.assertIsNone(breakdown["math_score"])

        response = self.client.get(reverse("global_event_result_root", args=[attempt.guest_token]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "sat/public_placement/result.html")
        self.assertContains(response, "Advanced")
        self.assertContains(response, "Reading and Writing score")
        self.assertContains(response, f"{breakdown['ebrw_score']} <small>/ 800</small>")
        self.assertContains(response, "2 / 2")
        self.assertContains(response, "Take the Math level check")
        self.assertNotContains(response, "phone number you provided")

    def test_returning_to_the_link_continues_the_same_attempt(self):
        first = self.start("english")
        page = self.client.get(reverse("public_placement_direct_english"))
        self.assertContains(page, "Continue the English level check")
        response = self.client.post(reverse("public_placement_direct_english"))
        self.assertRedirects(response, reverse("global_event_attempt_root", args=[first.guest_token]), fetch_redirect_response=False)
        self.assertEqual(GlobalEventAttempt.objects.count(), 1)

    def test_closed_when_no_placement_event_is_live(self):
        self.event.status = "completed"
        self.event.save(update_fields=["status"])
        page = self.client.get(reverse("public_placement_direct_math"))
        self.assertContains(page, "not open right now")
        response = self.client.post(reverse("public_placement_direct_math"))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(GlobalEventAttempt.objects.exists())

    def test_full_placement_attempts_are_unchanged(self):
        response = self.client.post(
            reverse("public_placement_start", args=[self.event.slug]),
            {"first_name": "Laylo", "last_name": "Aliyeva", "phone_number": "+998 91 111 22 33", "consent_to_contact": "1"},
        )
        self.assertEqual(response.status_code, 302)
        attempt = GlobalEventAttempt.objects.get()
        self.assertEqual(attempt.run_mode, GlobalEventAttempt.RUN_FULL)
        self.assertEqual(attempt_sequence(attempt), [("english", "m1"), ("math", "m1")])

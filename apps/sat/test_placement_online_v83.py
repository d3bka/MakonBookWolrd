"""V83: the online SATMakon placement test shows a 200-800 score for each subject, from
SATMakon's official tables stretched to 800. The offline placement test keeps Level 1-5."""
from datetime import timedelta

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.sat.guest_views import calculate_attempt_breakdown, finalize_attempt
from apps.sat.models import (
    English_Question, GlobalEvent, GlobalEventAnswer, Math_Question, PlacementTelegramNotification,
    PublicPlacementLead, Test,
)
from apps.sat.placement_online_scoring import (
    EBRW_SCORES, MATH_SCORES, is_online_placement, online_breakdown, section_result, to_sat_scale,
)
from apps.telegram_bot.placement_notifications import _format_message, _notification_snapshot


class TableTests(SimpleTestCase):
    def test_tables_match_the_official_file(self):
        self.assertEqual(sorted(EBRW_SCORES), list(range(28)))
        self.assertEqual(sorted(MATH_SCORES), list(range(39)))
        self.assertEqual((EBRW_SCORES[27], EBRW_SCORES[13], EBRW_SCORES[9], EBRW_SCORES[0]), (700, 540, 470, 200))
        self.assertEqual((MATH_SCORES[38], MATH_SCORES[23], MATH_SCORES[12], MATH_SCORES[0]), (750, 580, 460, 200))
        for table in (EBRW_SCORES, MATH_SCORES):
            values = [table[n] for n in sorted(table)]
            self.assertEqual(values, sorted(values))  # never goes down with more correct answers

    def test_both_subjects_reach_800_and_start_at_200(self):
        for section, top in (("english", 27), ("math", 38)):
            scores = [section_result(section, n, top)["score"] for n in range(top + 1)]
            self.assertEqual((scores[0], scores[-1]), (200, 800), section)
            self.assertEqual(scores, sorted(scores), section)
            self.assertTrue(all(score % 10 == 0 for score in scores), section)
        self.assertEqual(to_sat_scale(539, 750), 570)  # the odd 539 in the Math table becomes a normal score

    def test_breakdown(self):
        result = online_breakdown(["english", "math"], {"english": 18, "math": 9}, {"english": 27, "math": 38})
        english, math = result["sections"]
        self.assertEqual((english["score"], math["score"]), (680, 410))
        self.assertNotIn("level", english)
        self.assertEqual((result["total_score"], result["max_total"]), (1090, 1600))
        self.assertEqual(result["label"], "EBRW 680 · Math 410")

    def test_a_test_with_another_length_is_scaled(self):
        result = online_breakdown(["english"], {"english": 10}, {"english": 20})
        self.assertEqual(result["sections"][0]["score"], to_sat_scale(EBRW_SCORES[14], 700))  # 10/20 of 27 -> 14

    def test_which_events_are_online(self):
        class E:
            def __init__(self, name, kind="placement"):
                self.event_type, self.test = kind, type("T", (), {"name": name})()
        self.assertTrue(is_online_placement(E("Placement Test")))
        self.assertTrue(is_online_placement(E("Placement Test 2026")))
        self.assertFalse(is_online_placement(E("Placement Test Offline")))
        self.assertFalse(is_online_placement(E("Placement Test", kind="event")))
        self.assertFalse(is_online_placement(E("LEVEL CHECK")))


@override_settings(MAKONBOOK_GUEST_MODE_ENABLED=False, SITE_URL="https://makonbook.uz")
class OnlinePlacementResultTests(TestCase):
    test_name = "Placement Test"

    def setUp(self):
        cache.clear()
        self.test = Test.objects.create(name=self.test_name, is_available=True)
        self.english = [English_Question.objects.create(test=self.test, module="module_1", number=n, question=f"E{n}",
                                                        a="a", b="b", c="c", d="d", answer="A",
                                                        response_type="multiple_choice") for n in range(1, 28)]
        self.math = [Math_Question.objects.create(test=self.test, module="module_1", number=n, question=f"M{n}",
                                                  a="a", b="b", c="c", d="d", answer="B", written=False)
                     for n in range(1, 39)]
        now = timezone.now()
        self.event = GlobalEvent.objects.create(
            title="SATMakon Placement", slug="satmakon-online-placement", event_type=GlobalEvent.TYPE_PLACEMENT,
            test=self.test, is_public=True, status="live", start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=2), english_duration_minutes=30, math_duration_minutes=30,
        )

    def start(self):
        response = self.client.post(reverse("public_placement_start", args=[self.event.slug]), {
            "first_name": "Laylo", "last_name": "Aliyeva", "phone_number": "+998 91 111 22 33", "consent_to_contact": "1",
        })
        self.assertEqual(response.status_code, 302)
        return PublicPlacementLead.objects.select_related("attempt").get().attempt

    def answer(self, attempt, english_right, math_right):
        for index, question in enumerate(self.english):
            GlobalEventAnswer.objects.create(attempt=attempt, section="english", module="m1", question_id=question.pk,
                                             selected_answer="A" if index < english_right else "C")
        for index, question in enumerate(self.math):
            GlobalEventAnswer.objects.create(attempt=attempt, section="math", module="m1", question_id=question.pk,
                                             selected_answer="B" if index < math_right else "D")

    def test_scores_and_levels_per_subject(self):
        attempt = self.start()
        self.answer(attempt, english_right=12, math_right=30)
        finalize_attempt(attempt)
        attempt.refresh_from_db()
        breakdown = calculate_attempt_breakdown(attempt)
        self.assertEqual(breakdown["scoring_type"], "online_placement")
        self.assertEqual((breakdown["ebrw_score"], breakdown["math_score"]), (600, 690))
        self.assertEqual(attempt.score, 1290)

        page = self.client.get(reverse("global_event_result_root", args=[attempt.guest_token]))
        self.assertContains(page, "data-online-placement")
        self.assertContains(page, "600 <small>/ 800</small>")
        self.assertContains(page, "690 <small>/ 800</small>")
        self.assertContains(page, "out of 1600")
        self.assertContains(page, "12 / 27 correct")
        for word in ("Foundation", "Core", "Advanced", "Level 3"):
            self.assertNotContains(page, word)

    def test_managers_get_both_levels_in_telegram(self):
        attempt = self.start()
        self.answer(attempt, english_right=5, math_right=36)
        finalize_attempt(attempt)
        notice = PlacementTelegramNotification.objects.filter(kind=PlacementTelegramNotification.KIND_COMPLETED).first()
        message = _format_message(_notification_snapshot(notice.pk))
        self.assertIn("EBRW 380 · Math 780", message)


class OfflinePlacementUnchangedTests(OnlinePlacementResultTests):
    test_name = "Placement Test Offline"

    # The online-only checks do not apply to the offline test.
    test_scores_and_levels_per_subject = None
    test_managers_get_both_levels_in_telegram = None

    def test_the_offline_placement_keeps_level_1_to_5(self):
        attempt = self.start()
        self.answer(attempt, english_right=12, math_right=30)
        finalize_attempt(attempt)
        breakdown = calculate_attempt_breakdown(attempt)
        self.assertIsNone(breakdown["online_placement"])
        self.assertNotEqual(breakdown["scoring_type"], "online_placement")

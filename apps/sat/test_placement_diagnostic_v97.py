"""V97: tier-based placement, AI-checked written answers, JSON import and the admin Tests page."""
import io
import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat import ai_written_grading
from apps.sat.models import (
    English_Question, GlobalEvent, GlobalEventAnswer, GlobalEventAttempt, Test, TestImportJob, TestImportReview,
)
from apps.sat.placement_tiers import recommend_course
from apps.sat.json_test_import import JsonImportError, import_test_json
from apps.sat.test_import_service import publish_import_job


def build_test(data):
    """JSON → staging import → one approval → published test."""
    job = import_test_json(data)
    reviewer, _ = User.objects.get_or_create(username="v97_reviewer")
    TestImportReview.objects.update_or_create(job=job, reviewer=reviewer, defaults={"verdict": TestImportReview.VERDICT_APPROVED})
    job.refresh_review_status()
    return publish_import_job(job.pk)


def tiers(f=(0, 11), p=(0, 12), s=(0, 7)):
    return {"foundation": {"correct": f[0], "total": f[1]}, "pre_sat": {"correct": p[0], "total": p[1]},
            "sat": {"correct": s[0], "total": s[1]}}


class RubricTests(TestCase):
    """The cut-offs from the PDF rubric (30 questions: 11 / 12 / 7 per tier)."""

    def test_sat_course(self):
        self.assertEqual(recommend_course(24, 30, tiers((10, 11), (9, 12), (5, 7))), "sat")

    def test_high_total_but_weak_sat_tier_is_pre_sat(self):
        self.assertEqual(recommend_course(24, 30, tiers((11, 11), (9, 12), (4, 7))), "pre_sat")

    def test_pre_sat_course(self):
        self.assertEqual(recommend_course(14, 30, tiers((7, 11), (7, 12), (0, 7))), "pre_sat")

    def test_borderline_example_from_the_pdf_is_foundation(self):
        # "A student scoring 13 by clearing Tier 1 (10/11) while scoring only 3/12 on Tier 2 belongs in Foundation."
        self.assertEqual(recommend_course(13, 30, tiers((10, 11), (3, 12), (0, 7))), "foundation")

    # Borderline rule: from 22/30, about 60% on every tier is enough for the SAT Course.
    def test_borderline_example_a_23_points_is_sat(self):
        from apps.sat.placement_tiers import placement_rule
        self.assertEqual(placement_rule(23, 30, tiers((10, 11), (8, 12), (5, 7))), ("sat", "borderline"))

    def test_borderline_example_b_24_points_with_8_of_12_is_sat(self):
        self.assertEqual(recommend_course(24, 30, tiers((11, 11), (8, 12), (5, 7))), "sat")

    def test_more_points_never_give_a_lower_course(self):
        self.assertEqual(recommend_course(25, 30, tiers((11, 11), (8, 12), (6, 7))), "sat")

    def test_21_points_is_not_borderline(self):
        self.assertEqual(recommend_course(21, 30, tiers((9, 11), (7, 12), (5, 7))), "pre_sat")

    def test_borderline_needs_every_tier(self):
        self.assertEqual(recommend_course(23, 30, tiers((11, 11), (8, 12), (4, 7))), "pre_sat")
        self.assertEqual(recommend_course(23, 30, tiers((11, 11), (6, 12), (6, 7))), "foundation")  # rubric: Pre-SAT needs 7/12
        self.assertEqual(recommend_course(22, 30, tiers((6, 11), (11, 12), (5, 7))), "foundation")

    def test_low_total_is_foundation(self):
        self.assertEqual(recommend_course(11, 30, tiers((7, 11), (4, 12), (0, 7))), "foundation")


def sample_json(name="V97 Diagnostic"):
    return {
        "name": name, "test_type": "placement",
        "english": [
            {"number": 1, "tier": "foundation", "skill": "Past perfect", "passage": '"The train left. We arrived."',
             "question": "Combine using the past perfect.", "response_type": "ai_written",
             "answer": "The train had left before we arrived.", "accepted_answers": ["By the time we arrived, the train had left."],
             "grading_criteria": "had + past participle"},
            {"number": 2, "tier": "foundation", "skill": "Passive voice", "passage": '"They will announce it."',
             "question": "Rewrite in the passive.", "response_type": "ai_written", "answer": "It will be announced."},
            {"number": 3, "tier": "pre_sat", "skill": "Agreement", "question": "Pick one.",
             "choices": {"A": "is", "B": "are", "C": "were", "D": "be"}, "answer": "A"},
            {"number": 4, "tier": "sat", "skill": "Transitions", "question": "Pick one.",
             "choices": {"A": "However,", "B": "Thus,", "C": "Also,", "D": "Then,"}, "answer": "a"},
        ],
    }


class JsonImportTests(TestCase):
    def test_import_is_a_staging_job_and_publishes_as_a_tiered_placement_test(self):
        job = import_test_json(sample_json())
        self.assertTrue(job.is_json_import)
        self.assertEqual(job.target_test_type, "placement")
        self.assertFalse(Test.objects.filter(name="V97 Diagnostic").exists())
        staged = job.questions.get(number=1)
        self.assertEqual((staged.response_type, staged.placement_tier, staged.content_format), ("ai_written", "foundation", "makon"))
        test = build_test(sample_json("V97 Published"))
        self.assertEqual(test.test_type, "placement")
        q1 = English_Question.objects.get(test=test, number=1)
        self.assertEqual((q1.response_type, q1.placement_tier, q1.skill), ("ai_written", "foundation", "Past perfect"))
        self.assertEqual((q1.grading_criteria, q1.content_format), ("had + past participle", "makon"))
        self.assertTrue(q1.is_open_text)
        self.assertIn("By the time we arrived", q1.accepted_answers)
        self.assertEqual(English_Question.objects.get(test=test, number=4).answer, "A")

    def test_a_bad_question_imports_nothing(self):
        data = sample_json()
        data["english"][2]["choices"] = {"A": "is"}
        with self.assertRaises(JsonImportError):
            import_test_json(data)
        self.assertFalse(TestImportJob.objects.filter(name="V97 Diagnostic").exists())

    def test_duplicate_numbers_and_names_are_refused(self):
        data = sample_json()
        data["english"][1]["number"] = 1
        with self.assertRaises(JsonImportError):
            import_test_json(data)
        self.assertFalse(TestImportJob.objects.exists())
        build_test(sample_json())
        with self.assertRaises(JsonImportError):
            import_test_json(sample_json())


class DiagnosticEventTests(TestCase):
    def setUp(self):
        self.test = build_test(sample_json())
        now = timezone.now()
        self.event = GlobalEvent.objects.create(
            title="V97 Placement", slug="v97-placement", test=self.test, event_type=GlobalEvent.TYPE_PLACEMENT,
            start_at=now - timedelta(hours=1), end_at=now + timedelta(hours=4), status="live", is_public=True,
        )
        self.client.post(reverse("start_global_event_root", args=[self.event.slug]), {"full_name": "Malika"})
        self.attempt = GlobalEventAttempt.objects.get(event=self.event)
        self.q = {q.number: q for q in English_Question.objects.filter(test=self.test)}

    def submit(self, answers):
        page = reverse("global_event_attempt_root", args=[self.attempt.guest_token])
        self.assertEqual(self.client.get(page).status_code, 200)
        payload = [{"questionID": self.q[n].pk, "answer": a, "time_spent": 3} for n, a in answers.items()]
        response = self.client.post(reverse("submit_global_event_root", args=[self.attempt.guest_token]),
                                    json.dumps({"section": "english", "module": "m1", "answers": payload}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        return self.client.get(reverse("global_event_result_root", args=[self.attempt.guest_token]))

    def answer(self, number):
        return GlobalEventAnswer.objects.get(attempt=self.attempt, question_id=self.q[number].pk)

    def test_runner_shows_a_text_box_for_written_answers(self):
        page = self.client.get(reverse("global_event_attempt_root", args=[self.attempt.guest_token]))
        self.assertContains(page, '"response_type": "ai_written"')

    def test_matches_need_no_ai_and_the_ai_checks_the_rest_once(self):
        grader = mock.Mock(side_effect=lambda items: {
            item["id"]: {"correct": True, "feedback": "Correct future passive."} for item in items})
        with mock.patch.object(ai_written_grading, "grade_items", grader):
            result = self.submit({1: "by the time we arrived,  the train had LEFT", 2: "It will be announced by them",
                                  3: "A", 4: "B"})
            self.client.get(reverse("global_event_result_root", args=[self.attempt.guest_token]))
        self.assertEqual(grader.call_count, 1)
        sent = grader.call_args.args[0]
        self.assertEqual([item["student_answer"] for item in sent], ["It will be announced by them"])
        self.assertNotIn("Malika", json.dumps(sent))
        self.assertEqual(self.answer(1).grading["source"], "match")
        self.assertEqual(self.answer(2).grading["source"], "ai")
        self.assertTrue(self.answer(2).is_correct)

        diagnostic = result.context["diagnostic"]
        self.assertEqual((diagnostic["correct"], diagnostic["total"]), (3, 4))
        self.assertEqual({t["key"]: t["correct"] for t in diagnostic["tiers"]}, {"foundation": 2, "pre_sat": 1, "sat": 0})
        self.assertContains(result, diagnostic["course"])
        self.assertContains(result, "Correct future passive.")
        self.assertContains(result, "Score by level")

    def test_ai_outage_keeps_the_answer_pending_and_a_later_check_grades_it(self):
        failing = mock.Mock(side_effect=ai_written_grading.GradingUnavailable("timeout"))
        with mock.patch.object(ai_written_grading, "grade_items", failing):
            result = self.submit({1: "", 2: "Announced it will be", 3: "A", 4: "A"})
        self.assertEqual(self.answer(2).grading["source"], "pending")
        self.assertFalse(self.answer(2).is_correct)
        self.assertContains(result, "still being checked")

        # The retry waits a little; pretend the time passed.
        row = self.answer(2)
        row.grading["tried_at"] = 0
        row.save(update_fields=["grading"])
        wrong = mock.Mock(side_effect=lambda items: {item["id"]: {"correct": False, "feedback": "Word order."} for item in items})
        with mock.patch.object(ai_written_grading, "grade_items", wrong):
            from apps.sat.tasks import regrade_written_answers
            self.assertEqual(regrade_written_answers.apply(args=[self.attempt.pk]).get()["status"], "graded")
        self.assertEqual(self.answer(2).grading, {"source": "ai", "text": "Announced it will be", "correct": False,
                                                  "feedback": "Word order."})
        self.assertEqual(self.answer(1).grading["source"], "blank")

    def test_regular_events_are_unchanged(self):
        self.event.event_type = GlobalEvent.TYPE_EVENT
        self.event.save(update_fields=["event_type"])
        with mock.patch.object(ai_written_grading, "grade_items", return_value={}) as grader:
            grader.side_effect = lambda items: {item["id"]: {"correct": False, "feedback": ""} for item in items}
            result = self.submit({1: "", 2: "", 3: "A", 4: ""})
        self.assertIsNone(result.context["diagnostic"])


class GraderParsingTests(TestCase):
    def setUp(self):
        self.question = English_Question(passage="P", question="Q", answer="Model", accepted_answers="Alt", grading_criteria="C")

    def test_incomplete_ai_answer_counts_as_unavailable(self):
        items = [ai_written_grading.build_item(1, self.question, "x"), ai_written_grading.build_item(2, self.question, "y")]
        with mock.patch.object(ai_written_grading, "call_provider", return_value=[{"id": "1", "correct": True, "feedback": "ok"}]):
            with self.assertRaises(ai_written_grading.GradingUnavailable):
                ai_written_grading.grade_items(items)

    def test_provider_errors_become_unavailable(self):
        items = [ai_written_grading.build_item(1, self.question, "x")]
        with mock.patch.object(ai_written_grading, "call_provider", side_effect=RuntimeError("HTTP 500")):
            with self.assertRaises(ai_written_grading.GradingUnavailable):
                ai_written_grading.grade_items(items)

    def test_only_true_counts_as_correct(self):
        items = [ai_written_grading.build_item(1, self.question, "x")]
        with mock.patch.object(ai_written_grading, "call_provider", return_value=[{"id": "1", "correct": "yes", "feedback": "f"}]):
            self.assertEqual(ai_written_grading.grade_items(items), {"1": {"correct": False, "feedback": "f"}})


class AdminTestsPageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("v97_admin", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)
        build_test(sample_json("V97 Listed"))
        Test.objects.create(name="V97 EMPTY", is_available=True)

    def test_list_filters_and_detail(self):
        page = self.client.get(reverse("admin_tests"))
        self.assertContains(page, "V97 Listed")
        self.assertContains(page, "No questions")
        page = self.client.get(reverse("admin_tests"), {"type": "placement"})
        self.assertContains(page, "V97 Listed")
        self.assertNotContains(page, "V97 EMPTY")
        page = self.client.get(reverse("admin_tests"), {"state": "empty"})
        self.assertContains(page, "V97 EMPTY")
        self.assertNotContains(page, "V97 Listed</a>")
        detail = self.client.get(reverse("admin_test_detail", args=["V97 Listed"]))
        self.assertContains(detail, "Questions by module")
        self.assertEqual(detail.context["modules"]["english"]["m1"], 4)

    def test_json_upload(self):
        upload = SimpleUploadedFile("t.json", json.dumps(sample_json("V97 Uploaded")).encode(), content_type="application/json")
        response = self.client.post(reverse("admin_test_import_json"), {"file": upload})
        job = TestImportJob.objects.get(name="V97 Uploaded")
        self.assertRedirects(response, reverse("manager_test_import_detail_root", args=[job.pk]), fetch_redirect_response=False)
        bad = SimpleUploadedFile("t.json", b"{not json", content_type="application/json")
        self.client.post(reverse("admin_test_import_json"), {"file": bad})
        self.assertEqual(TestImportJob.objects.filter(name__startswith="V97 Uploaded").count(), 1)

    def test_teachers_cannot_import(self):
        teacher = User.objects.create_user("v97_t", password="x")
        self.client.force_login(teacher)
        upload = SimpleUploadedFile("t.json", json.dumps(sample_json("V97 Sneaky")).encode())
        self.client.post(reverse("admin_test_import_json"), {"file": upload})
        self.assertFalse(TestImportJob.objects.filter(name="V97 Sneaky").exists())

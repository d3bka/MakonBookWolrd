"""V97: imports carry written answers / placement levels, and the AI solves every question before publishing."""
import json
from unittest import mock

import fitz
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.sat.json_test_import import import_test_json
from apps.sat.models import English_Question, StudentPracticeTestAccess, Test, TestImportJob, TestImportReview
from apps.sat.test_import_service import _parse_structured_pdf

AI_ON = dict(TEST_IMPORT_REQUIRE_AI_AUDIT=True, QUESTION_AUDIT_PROVIDER="deepseek", DEEPSEEK_API_KEY="test-only-key")


def pdf_bytes(lines):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 40
    for line in lines:
        page.insert_text((45, y), line, fontsize=9)
        y += 15
    data = doc.tobytes()
    doc.close()
    return data


class StructuredPlacementMarkerTests(SimpleTestCase):
    def test_written_question_level_skill_and_test_type_are_read(self):
        data = pdf_bytes([
            "[[MAKONBOOK_STRUCTURED_PDF:2]]", "[[SECTION:EBRW]]", "[[TEST_TYPE:PLACEMENT]]", "[[MODULE:1]]",
            "[[QUESTION:1]]", "[[TYPE:WRITTEN]]", "[[LEVEL:FOUNDATION]]", "[[SKILL:Past perfect]]",
            "[[PASSAGE]]", "Combine: The train left. We arrived.", "[[/PASSAGE]]",
            "[[PROMPT]][[/PROMPT]]", "[[A]][[/A]]", "[[B]][[/B]]", "[[C]][[/C]]", "[[D]][[/D]]",
            "[[ANSWER]]", "The train had left before we arrived.", "[[/ANSWER]]",
            "[[ACCEPTED]]", "By the time we arrived, the train had left. [[OR]] When we arrived, the", "train had already left.", "[[/ACCEPTED]]",
            "[[CRITERIA]]", "Uses had + past participle for the earlier action.", "[[/CRITERIA]]",
            "[[EXPLANATION]][[/EXPLANATION]]", "[[END_QUESTION]]",
            "[[QUESTION:2]]", "[[TYPE:MCQ]]", "[[LEVEL:PRE-SAT]]", "[[SKILL:Transitions]]",
            "[[PASSAGE]]Text.[[/PASSAGE]]", "[[PROMPT]]Which choice?[[/PROMPT]]",
            "[[A]]a[[/A]]", "[[B]]b[[/B]]", "[[C]]c[[/C]]", "[[D]]d[[/D]]", "[[ANSWER]]C[[/ANSWER]]",
            "[[EXPLANATION]][[/EXPLANATION]]", "[[END_QUESTION]]",
        ])
        parsed, meta = _parse_structured_pdf(data, "english")
        self.assertEqual(meta["test_type"], "placement")
        written, mcq = parsed[0][1], parsed[1][1]
        self.assertEqual((written["response_type"], written["placement_tier"], written["skill"]), ("ai_written", "foundation", "Past perfect"))
        self.assertEqual(written["answer"], "The train had left before we arrived.")
        self.assertEqual(written["accepted_answers"].split("\n"), [
            "By the time we arrived, the train had left.", "When we arrived, the train had already left.",
        ])
        self.assertEqual(written["grading_criteria"], "Uses had + past participle for the earlier action.")
        self.assertEqual((mcq["response_type"], mcq["placement_tier"], mcq["skill"]), ("multiple_choice", "pre_sat", "Transitions"))

    def test_old_pdfs_are_unchanged(self):
        data = pdf_bytes([
            "[[MAKONBOOK_STRUCTURED_PDF:2]]", "[[SECTION:EBRW]]", "[[MODULE:1]]", "[[QUESTION:1]]", "[[TYPE:SPR]]",
            "[[PROMPT]]Type the word.[[/PROMPT]]", "[[ANSWER]]cat[[/ANSWER]]", "[[END_QUESTION]]",
        ])
        parsed, meta = _parse_structured_pdf(data, "english")
        self.assertEqual(meta["test_type"], "")
        item = parsed[0][1]
        self.assertEqual((item["response_type"], item["placement_tier"], item["accepted_answers"]), ("open_text", "", ""))


def sample(name="V97 AI Check"):
    return {
        "name": name, "test_type": "placement",
        "english": [
            {"number": 1, "tier": "foundation", "skill": "Past perfect", "question": "Combine using the past perfect.",
             "passage": "| Year | Visitors |\n| 2019 | 1,200 |", "response_type": "ai_written",
             "answer": "The train had left before we arrived.", "grading_criteria": "had + past participle"},
            {"number": 2, "tier": "pre_sat", "skill": "Agreement", "question": "Pick one.",
             "choices": {"A": "is", "B": "are", "C": "were", "D": "be"}, "answer": "A"},
        ],
    }


def ai_answers(verdicts):
    """Fake provider: verdicts maps question number → 'ok' / 'issue' / 'uncertain'."""
    def fake(batch, model=None):
        rows = []
        for item in batch:
            verdict = verdicts.get(item["number"], "ok")
            rows.append({
                "id": item["id"], "section": item["section"], "verdict": verdict,
                "severity": "none" if verdict == "ok" else "high", "confidence": 0.9, "issue_types": [],
                "summary": "Matches." if verdict == "ok" else "The key looks wrong.",
                "verified_answer": item["stored_answer"] if verdict == "ok" else "B", "recommended_fix": "",
            })
        return rows
    return fake


@override_settings(**AI_ON)
class ImportAiCheckTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("v97_manager", password="x", is_staff=True)
        self.client.force_login(self.manager)
        self.job = import_test_json(sample())
        self.detail = reverse("manager_test_import_detail_root", args=[self.job.pk])

    def run_ai(self, verdicts=None):
        with mock.patch("apps.sat.question_audit.call_audit_model", side_effect=ai_answers(verdicts or {})) as fake:
            for _ in range(5):
                data = self.client.post(reverse("manager_test_import_audit_batch_root", args=[self.job.pk]), {"restart": "0"}).json()
                if data.get("complete"):
                    break
        sent = json.dumps([call.args[0] for call in fake.call_args_list])
        self.assertIn("had + past participle", sent)  # the AI sees the grading criteria of written answers
        self.job.refresh_from_db()
        return data

    def approve(self):
        self.client.post(reverse("manager_test_import_review_root", args=[self.job.pk]), {"verdict": "approved"})
        self.job.refresh_from_db()

    def test_the_check_starts_by_itself_and_blocks_publishing_until_it_finishes(self):
        page = self.client.get(self.detail)
        self.assertContains(page, "data-audit-autostart")
        self.assertContains(page, "Wait for the AI answer check to finish.")
        self.approve()
        self.assertEqual(self.job.ai_check_state, TestImportJob.AI_PENDING)
        self.assertNotEqual(self.job.status, TestImportJob.STATUS_READY_TO_PUBLISH)

    def test_clean_check_and_one_person_publish_a_placement_test(self):
        self.run_ai()
        self.assertEqual(self.job.ai_check_state, TestImportJob.AI_CLEAN)
        self.assertNotEqual(self.job.status, TestImportJob.STATUS_READY_TO_PUBLISH)  # the AI alone never publishes
        self.assertNotContains(self.client.get(self.detail), "data-audit-autostart")
        self.approve()
        self.assertEqual(self.job.status, TestImportJob.STATUS_READY_TO_PUBLISH)
        self.assertEqual((self.job.approval_count, self.job.approval_target), (2, 2))
        self.client.post(reverse("manager_test_import_publish_root", args=[self.job.pk]))
        test = Test.objects.get(name="V97 AI Check")
        self.assertEqual(test.test_type, Test.TYPE_PLACEMENT)
        self.assertFalse(StudentPracticeTestAccess.objects.filter(test=test).exists())
        q1 = English_Question.objects.get(test=test, number=1)
        self.assertEqual((q1.response_type, q1.placement_tier, q1.content_format), ("ai_written", "foundation", "makon"))

    def test_a_flagged_question_blocks_until_a_manager_keeps_the_key(self):
        self.run_ai({2: "issue"})
        self.assertEqual(self.job.ai_check_state, TestImportJob.AI_ISSUES)
        self.approve()
        self.assertNotEqual(self.job.status, TestImportJob.STATUS_READY_TO_PUBLISH)
        page = self.client.get(self.detail)
        self.assertContains(page, "AI found a problem")
        self.assertContains(page, "Decline")
        flagged = self.job.questions.get(number=2)
        self.client.post(reverse("manager_test_import_ai_decision_root", args=[self.job.pk, flagged.pk]), {"decision": "decline"})
        flagged.refresh_from_db()
        self.assertEqual(flagged.audit_verdict, "ok")
        self.assertIn("Kept as is by v97_manager", flagged.audit_summary)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, TestImportJob.STATUS_READY_TO_PUBLISH)

    def test_support_teachers_cannot_confirm_keys(self):
        self.run_ai({2: "issue"})
        teacher = User.objects.create_user("v97_support", password="x")
        self.client.force_login(teacher)
        flagged = self.job.questions.get(number=2)
        response = self.client.post(reverse("manager_test_import_ai_decision_root", args=[self.job.pk, flagged.pk]), {"decision": "decline"})
        self.assertEqual(response.status_code, 403)
        flagged.refresh_from_db()
        self.assertEqual(flagged.audit_verdict, "issue")

    def test_editing_a_question_checks_it_again(self):
        self.run_ai()
        question = self.job.questions.get(number=2)
        form = {
            "number": 2, "question": "Pick one.", "a": "is", "b": "are", "c": "were", "d": "be", "answer": "B",
            "response_type": "multiple_choice", "source_page": 1, "placement_tier": "pre_sat", "skill": "Agreement",
        }
        self.client.post(reverse("manager_test_import_question_edit_root", args=[self.job.pk, question.pk]), form)
        question.refresh_from_db()
        self.assertEqual((question.answer, question.audit_verdict), ("B", ""))
        self.job.refresh_from_db()
        self.assertEqual(self.job.ai_check_state, TestImportJob.AI_PENDING)
        self.assertContains(self.client.get(self.detail), "data-audit-autostart")

    def test_preview_renders_makonbook_text(self):
        page = self.client.get(reverse("manager_test_import_preview_root", args=[self.job.pk]))
        first = next(q for q in page.context["questions_payload"] if q["number"] == 1)
        self.assertIn("<table", first["html"]["passage"])
        self.assertEqual(first["response_type"], "ai_written")

    def test_import_center_accepts_json(self):
        upload = SimpleUploadedFile("t.json", json.dumps(sample("V97 From Center")).encode(), content_type="application/json")
        response = self.client.post(reverse("manager_test_import_create_json_root"), {"file": upload})
        job = TestImportJob.objects.get(name="V97 From Center")
        self.assertRedirects(response, reverse("manager_test_import_detail_root", args=[job.pk]), fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse("manager_test_import_create_root")), "Import from JSON")


class ImportWithoutAiKeyTests(TestCase):
    @override_settings(TEST_IMPORT_REQUIRE_AI_AUDIT=True, QUESTION_AUDIT_PROVIDER="deepseek", DEEPSEEK_API_KEY="")
    def test_without_a_provider_key_the_check_is_optional(self):
        manager = User.objects.create_user("v97_manager2", password="x", is_staff=True)
        job = import_test_json(sample("V97 No Key"))
        self.assertEqual(job.ai_check_state, TestImportJob.AI_OFF)
        TestImportReview.objects.create(job=job, reviewer=manager, verdict=TestImportReview.VERDICT_APPROVED)
        self.assertEqual(job.refresh_review_status(), TestImportJob.STATUS_READY_TO_PUBLISH)

"""V98: SAT categories on imports, and AI fixes that a manager approves or declines."""
import json
from unittest import mock

import fitz
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.sat.json_test_import import JsonImportError, import_test_json
from apps.sat.models import English_Question, Math_Question, Test, TestImportJob, TestImportReview
from apps.sat.sat_taxonomy import canonical_domain, canonical_skill
from apps.sat.test_import_service import _parse_structured_pdf, parse_pipe_table, render_table_svg

AI_ON = dict(TEST_IMPORT_REQUIRE_AI_AUDIT=True, QUESTION_AUDIT_PROVIDER="deepseek", DEEPSEEK_API_KEY="test-only-key")
EMPTY_FIX = {name: "" for name in ("question", "passage", "a", "b", "c", "d", "answer", "explanation", "table")}


class TaxonomyTests(SimpleTestCase):
    def test_official_names_and_aliases(self):
        self.assertEqual(canonical_domain("algebra", "math"), "Algebra")
        self.assertEqual(canonical_domain("Geometry", "math"), "Geometry and Trigonometry")
        self.assertEqual(canonical_domain("PSDA", "math"), "Problem-Solving and Data Analysis")
        self.assertEqual(canonical_domain("Algebra", "english"), "")  # wrong section
        self.assertEqual(canonical_domain("Cooking", None), "")
        self.assertEqual(canonical_skill("Algebra", "linear  functions"), "Linear functions")
        self.assertEqual(canonical_skill("Algebra", "Slope tricks"), "Slope tricks")

    def test_pipe_table_and_svg(self):
        rows = parse_pipe_table("| Year | Visitors |\n|---|---|\n| 2019 | 1,200 |")
        self.assertEqual(rows, [["Year", "Visitors"], ["2019", "1,200"]])
        svg = render_table_svg("| Year | <b>x</b> |\n| 2019 | 1,200 |").decode()
        self.assertIn("<svg", svg)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", svg)
        self.assertEqual(parse_pipe_table("just text"), [])

    def test_structured_pdf_reads_domain_and_skill(self):
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        lines = [
            "[[MAKONBOOK_STRUCTURED_PDF:2]]", "[[SECTION:MATH]]", "[[MODULE:1]]", "[[QUESTION:1]]", "[[TYPE:MCQ]]",
            "[[DOMAIN:geometry]]", "[[SKILL:circles]]", "[[PROMPT]]What is the radius?[[/PROMPT]]",
            "[[A]]1[[/A]]", "[[B]]2[[/B]]", "[[C]]3[[/C]]", "[[D]]4[[/D]]", "[[ANSWER]]B[[/ANSWER]]", "[[END_QUESTION]]",
            "[[QUESTION:2]]", "[[TYPE:MCQ]]", "[[DOMAIN:Cooking]]", "[[PROMPT]]x?[[/PROMPT]]",
            "[[A]]1[[/A]]", "[[B]]2[[/B]]", "[[C]]3[[/C]]", "[[D]]4[[/D]]", "[[ANSWER]]A[[/ANSWER]]", "[[END_QUESTION]]",
        ]
        for i, line in enumerate(lines):
            page.insert_text((45, 40 + 15 * i), line, fontsize=9)
        parsed, _ = _parse_structured_pdf(doc.tobytes(), "math")
        doc.close()
        first, second = parsed[0][1], parsed[1][1]
        self.assertEqual((first["domain_name"], first["skill"]), ("Geometry and Trigonometry", "Circles"))
        self.assertEqual((second["domain_name"], second["declared_domain"]), ("", "Cooking"))


def sat_json(name="V98 SAT"):
    return {
        "name": name, "test_type": "regular",
        "english": [
            {"number": 1, "question": "Which choice completes the text?", "passage": "The data in the table show growth.",
             "choices": {"A": "rose", "B": "fell", "C": "stayed", "D": "vanished"}, "answer": "A",
             "domain": "Craft and Structure", "skill": "Words in Context"},
            {"number": 2, "question": "Which choice best states the main idea?", "passage": "Bees pollinate crops.",
             "choices": {"A": "Bees", "B": "Crops", "C": "Rain", "D": "Soil"}, "answer": "C"},
        ],
        "math": [
            {"number": 1, "question": "If 3x + 5 = 20, what is x?", "choices": {"A": "3", "B": "5", "C": "15", "D": "25"},
             "answer": "B", "domain": "Algebra", "skill": "Linear equations in one variable"},
        ],
    }


def fake_ai(by_number):
    """by_number: {(section, number): finding overrides}."""
    def fake(batch, model=None):
        rows = []
        for item in batch:
            row = {
                "id": item["id"], "section": item["section"], "verdict": "ok", "severity": "none", "confidence": 0.9,
                "issue_types": [], "summary": "Matches.", "verified_answer": item["stored_answer"], "recommended_fix": "",
                "domain": item.get("domain", ""), "skill": item.get("skill", ""), "proposed_fix": dict(EMPTY_FIX),
            }
            override = by_number.get((item["section"], item["number"]), {})
            fix = override.pop("proposed_fix", {}) if override else {}
            row.update(override)
            row["proposed_fix"].update(fix)
            rows.append(row)
        return rows
    return fake


@override_settings(**AI_ON)
class AiFixDecisionTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("v98_manager", password="x", is_staff=True)
        self.client.force_login(self.manager)

    def import_and_check(self, data, findings):
        job = import_test_json(data)
        with mock.patch("apps.sat.question_audit.call_audit_model", side_effect=fake_ai(findings)):
            for _ in range(5):
                result = self.client.post(reverse("manager_test_import_audit_batch_root", args=[job.pk]), {"restart": "0"}).json()
                if result.get("complete"):
                    break
        job.refresh_from_db()
        return job

    def decide(self, job, question, decision):
        return self.client.post(reverse("manager_test_import_ai_decision_root", args=[job.pk, question.pk]), {"decision": decision})

    def test_json_import_keeps_categories_and_rejects_unknown_domains(self):
        job = import_test_json(sat_json())
        q = job.questions.get(section="math", number=1)
        self.assertEqual((q.domain_name, q.skill), ("Algebra", "Linear equations in one variable"))
        bad = sat_json("V98 Bad")
        bad["math"][0]["domain"] = "Cooking"
        with self.assertRaises(JsonImportError):
            import_test_json(bad)

    def test_wrong_key_and_broken_choice_are_fixed_only_after_approve(self):
        job = self.import_and_check(sat_json(), {
            ("english", 2): {"verdict": "issue", "severity": "high", "summary": "The key is wrong; the text is about bees.",
                             "domain": "Information and Ideas", "skill": "Central Ideas and Details",
                             "proposed_fix": {"answer": "a", "d": "Wind"}},
        })
        q = job.questions.get(section="english", number=2)
        self.assertEqual(q.ai_proposal, {"answer": "A", "d": "Wind", "domain_name": "Information and Ideas", "skill": "Central Ideas and Details"})
        self.assertEqual((q.answer, q.d), ("C", "Soil"))  # nothing changes before a decision
        self.assertEqual(job.ai_check_state, TestImportJob.AI_ISSUES)
        page = self.client.get(reverse("manager_test_import_detail_root", args=[job.pk]))
        self.assertContains(page, "Needs your decision")
        self.assertContains(page, "AI suggests")
        self.decide(job, q, "approve")
        q.refresh_from_db()
        self.assertEqual((q.answer, q.d, q.domain_name, q.audit_verdict, q.ai_proposal_status), ("A", "Wind", "Information and Ideas", "ok", "approved"))
        job.refresh_from_db()
        self.assertEqual(job.ai_check_state, TestImportJob.AI_CLEAN)

    def test_approving_only_a_category_does_not_clear_a_missing_graph(self):
        job = self.import_and_check(sat_json(), {
            ("english", 2): {"verdict": "issue", "issue_types": ["missing_information"],
                             "summary": "The graph is missing.", "domain": "Information and Ideas"},
        })
        q = job.questions.get(section="english", number=2)
        page = self.client.get(reverse("manager_test_import_detail_root", args=[job.pk]))
        self.assertContains(page, "Approve category")
        self.assertContains(page, "The AI cannot fix this itself")
        self.decide(job, q, "approve")
        q.refresh_from_db()
        self.assertEqual((q.domain_name, q.audit_verdict), ("Information and Ideas", "issue"))
        job.refresh_from_db()
        self.assertEqual(job.ai_check_state, TestImportJob.AI_ISSUES)
        self.decide(job, q, "decline")
        job.refresh_from_db()
        self.assertEqual(job.ai_check_state, TestImportJob.AI_CLEAN)

    def test_decline_keeps_the_question(self):
        job = self.import_and_check(sat_json(), {
            ("english", 2): {"verdict": "issue", "proposed_fix": {"answer": "A"}},
        })
        q = job.questions.get(section="english", number=2)
        self.decide(job, q, "decline")
        q.refresh_from_db()
        self.assertEqual((q.answer, q.audit_verdict, q.ai_proposal_status), ("C", "ok", "declined"))
        self.assertIn("Kept as is by v98_manager", q.audit_summary)

    def test_missing_table_becomes_the_question_picture(self):
        data = sat_json()
        data["english"][0]["passage"] = "Visitors: 2019 had 1,200 and 2020 had 1,500."
        job = import_test_json(data)
        job.questions.update(content_format="legacy")  # like a Structured PDF import
        with mock.patch("apps.sat.question_audit.call_audit_model", side_effect=fake_ai({
            ("english", 1): {"verdict": "issue", "issue_types": ["missing_information"],
                             "proposed_fix": {"table": "| Year | Visitors |\n| 2019 | 1,200 |\n| 2020 | 1,500 |"}},
        })):
            while not self.client.post(reverse("manager_test_import_audit_batch_root", args=[job.pk]), {"restart": "0"}).json().get("complete"):
                pass
        q = job.questions.get(section="english", number=1)
        self.assertIn("table", q.ai_proposal)
        self.decide(job, q, "approve")
        q.refresh_from_db()
        self.assertTrue(q.graph)
        self.assertTrue(q.image.name.endswith(".svg"))

    def test_category_and_explanation_suggestions_are_approved_in_bulk(self):
        job = self.import_and_check(sat_json(), {
            ("english", 2): {"domain": "Information and Ideas", "skill": "central ideas and details",
                             "proposed_fix": {"explanation": "The passage is about bees, so A."}},
            ("english", 1): {"proposed_fix": {"explanation": "Rose fits the growth."}},
        })
        self.assertEqual(job.ai_check_state, TestImportJob.AI_ISSUES)  # undecided suggestions wait
        page = self.client.get(reverse("manager_test_import_detail_root", args=[job.pk]))
        self.assertContains(page, "Categories and explanations")
        self.assertNotContains(page, "Needs your decision")
        self.client.post(reverse("manager_test_import_ai_approve_suggestions_root", args=[job.pk]))
        q2 = job.questions.get(section="english", number=2)
        self.assertEqual((q2.domain_name, q2.skill), ("Information and Ideas", "Central Ideas and Details"))
        self.assertEqual(q2.explanation, "The passage is about bees, so A.")
        job.refresh_from_db()
        self.assertEqual(job.ai_check_state, TestImportJob.AI_CLEAN)

    def test_an_existing_explanation_is_not_rewritten_without_a_problem(self):
        data = sat_json()
        data["english"][0]["explanation"] = "Original explanation."
        job = self.import_and_check(data, {("english", 1): {"proposed_fix": {"explanation": "AI rewrite."}}})
        self.assertEqual(job.questions.get(section="english", number=1).ai_proposal, {})

    def test_publish_sets_domain_and_skill(self):
        job = self.import_and_check(sat_json(), {
            ("english", 2): {"domain": "Information and Ideas", "skill": "Central Ideas and Details"},
        })
        self.client.post(reverse("manager_test_import_ai_approve_suggestions_root", args=[job.pk]))
        TestImportReview.objects.create(job=job, reviewer=self.manager, verdict=TestImportReview.VERDICT_APPROVED)
        self.assertEqual(job.refresh_review_status(), TestImportJob.STATUS_READY_TO_PUBLISH)
        self.client.post(reverse("manager_test_import_publish_root", args=[job.pk]))
        test = Test.objects.get(name="V98 SAT")
        q = English_Question.objects.select_related("domain", "type").get(test=test, number=2)
        self.assertEqual((q.domain.name, q.type.name, q.type.domain.name), ("Information and Ideas", "Central Ideas and Details", "Information and Ideas"))
        m = Math_Question.objects.select_related("domain", "type").get(test=test, number=1)
        self.assertEqual((m.domain.name, m.type.name), ("Algebra", "Linear equations in one variable"))

    def test_a_question_that_already_has_a_category_gets_no_suggestion(self):
        job = self.import_and_check(sat_json("V98 Seen"), {("math", 1): {"domain": "Advanced Math", "skill": "Nonlinear functions"}})
        self.assertEqual(job.questions.get(section="math", number=1).ai_proposal, {})

    def test_support_teachers_cannot_decide(self):
        job = self.import_and_check(sat_json(), {("english", 2): {"verdict": "issue", "proposed_fix": {"answer": "A"}}})
        self.client.force_login(User.objects.create_user("v98_support", password="x"))
        q = job.questions.get(section="english", number=2)
        self.assertEqual(self.decide(job, q, "approve").status_code, 403)
        self.assertEqual(self.client.post(reverse("manager_test_import_ai_approve_suggestions_root", args=[job.pk])).status_code, 403)
        q.refresh_from_db()
        self.assertEqual(q.answer, "C")


class AiPayloadTests(TestCase):
    def test_payload_carries_category_and_instructions_list_the_domains(self):
        from apps.sat.question_audit import AUDIT_SCHEMA, SYSTEM_INSTRUCTIONS
        from apps.sat.test_import_service import _audit_payload_for_questions

        job = import_test_json(sat_json("V98 Payload"))
        payload = _audit_payload_for_questions(job, list(job.questions.filter(section="math")))
        self.assertEqual((payload[0]["domain"], payload[0]["skill"]), ("Algebra", "Linear equations in one variable"))
        self.assertIn("Problem-Solving and Data Analysis", SYSTEM_INSTRUCTIONS)
        item = AUDIT_SCHEMA["properties"]["questions"]["items"]
        self.assertIn("proposed_fix", item["required"])
        json.dumps(AUDIT_SCHEMA)

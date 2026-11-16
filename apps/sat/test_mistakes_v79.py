"""V79: Mistakes — wrong or skipped practice-test questions, retried until fixed."""
import json
import uuid

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from apps.sat.models import English_Question, Math_Question, StudentMistake, Test, TestModule, TestReview


class MistakesTests(TestCase):
    def setUp(self):
        self.kid = User.objects.create_user("v79_kid", password="x")
        self.test = Test.objects.create(name="DAY1", is_available=True)
        self.e1 = English_Question.objects.create(test=self.test, module="module_1", number=1, question="E1",
                                                  a="a", b="b", c="c", d="d", answer="A", response_type="multiple_choice")
        self.e2 = English_Question.objects.create(test=self.test, module="module_1", number=2, question="E2",
                                                  a="a", b="b", c="c", d="d", answer="B", response_type="multiple_choice")
        self.e3 = English_Question.objects.create(test=self.test, module="module_1", number=3, question="E3",
                                                  a="a", b="b", c="c", d="d", answer="C", response_type="multiple_choice")
        self.m1 = Math_Question.objects.create(test=self.test, module="module_1", number=1, question="2+3?",
                                               a="4", b="5", c="6", d="7", answer="B", written=False)
        self.m2 = Math_Question.objects.create(test=self.test, module="module_1", number=2, question="10/4?",
                                               answer="2.5", written=True)

    def attempt(self, answers, *, test=None, user=None):
        """answers: {question: response}; one scored attempt with both sections' module 1."""
        test, user, attempt_id = test or self.test, user or self.kid, uuid.uuid4()
        for section, model in (("english", English_Question), ("math", Math_Question)):
            rows = [{"questionID": q.pk, "answer": a} for q, a in answers.items() if isinstance(q, model)]
            TestModule.objects.create(test=test, user=user, section=section, module="m1", attempt_id=attempt_id,
                                      answers=json.dumps({"answers": rows}))
        return TestReview.objects.create(test=test, user=user, key=f"v79-{attempt_id}", attempt_id=attempt_id, score=900)

    def open_page(self):
        self.client.force_login(self.kid)
        return self.client.get(reverse("student_mistakes_root"))

    def mistake(self, question, section):
        return StudentMistake.objects.get(user=self.kid, section=section, question_id=question.pk)

    def check(self, question, section, answer):
        return self.client.post(reverse("student_mistake_check_root"),
                                json.dumps({"section": section, "question_id": question.pk, "answer": answer}),
                                content_type="application/json")

    def test_wrong_and_skipped_answers_become_mistakes(self):
        self.attempt({self.e1: "A", self.e2: "D", self.m1: "B", self.m2: "3"})   # e3 skipped
        page = self.open_page()
        self.assertEqual(page.status_code, 200)
        wrong = set(StudentMistake.objects.filter(user=self.kid).values_list("section", "question_id"))
        self.assertEqual(wrong, {("english", self.e2.pk), ("english", self.e3.pk), ("math", self.m2.pk)})
        self.assertEqual(self.mistake(self.e3, "english").last_answer, "")
        self.assertContains(page, "skipped")
        self.open_page()  # an attempt is scanned only once
        self.assertEqual(self.mistake(self.e2, "english").wrong_count, 1)

    def test_only_practice_tests_count(self):
        placement = Test.objects.create(name="PLACEMENT", is_available=True, test_type=Test.TYPE_PLACEMENT)
        q = English_Question.objects.create(test=placement, module="module_1", number=1, question="P",
                                            a="a", b="b", answer="A", response_type="multiple_choice")
        self.attempt({q: "B"}, test=placement)
        TestReview.objects.create(test=self.test, user=self.kid, key="v79-unscored", attempt_id=uuid.uuid4(), score=None)
        self.open_page()
        self.assertFalse(StudentMistake.objects.filter(user=self.kid).exists())

    def test_one_correct_retry_fixes_and_a_wrong_one_reopens(self):
        self.attempt({self.e1: "A", self.e2: "D", self.e3: "C", self.m1: "B", self.m2: "2.5"})
        self.open_page()
        response = self.check(self.e2, "english", "B").json()
        self.assertEqual((response["correct"], response["status"]), (True, "fixed"))
        response = self.check(self.e2, "english", "A").json()
        self.assertEqual((response["correct"], response["status"]), (False, "open"))
        self.assertEqual(self.mistake(self.e2, "english").wrong_count, 2)

    def test_written_math_answers_are_checked_like_the_test(self):
        self.attempt({self.m2: "3"})
        self.open_page()
        self.assertTrue(self.check(self.m2, "math", "5/2").json()["correct"])
        self.assertEqual(self.mistake(self.m2, "math").status, StudentMistake.STATUS_FIXED)

    def test_a_later_attempt_fixes_or_reopens(self):
        self.attempt({self.e2: "D"})
        self.open_page()
        self.attempt({self.e2: "B"})          # right this time
        self.open_page()
        self.assertEqual(self.mistake(self.e2, "english").status, StudentMistake.STATUS_FIXED)
        self.attempt({self.e2: "C"})          # wrong again
        self.open_page()
        row = self.mistake(self.e2, "english")
        self.assertEqual((row.status, row.wrong_count), (StudentMistake.STATUS_OPEN, 2))

    def test_fix_all_includes_fixed_ones_and_open_mode_does_not(self):
        self.attempt({self.e1: "B", self.e2: "D", self.e3: "A", self.m1: "B", self.m2: "2.5"})
        self.open_page()
        self.check(self.e1, "english", "A")   # fixed once
        drill = reverse("student_mistakes_drill_root")
        all_ids = [row.question_id for row in self.client.get(drill, {"mode": "all"}).context["drill_rows"]]
        self.assertEqual(all_ids, [self.e2.pk, self.e3.pk, self.e1.pk])  # open first, then fixed once
        open_ids = [row.question_id for row in self.client.get(drill, {"mode": "open"}).context["drill_rows"]]
        self.assertNotIn(self.e1.pk, open_ids)
        one = self.client.get(drill, {"mistake": self.mistake(self.e3, "english").pk}).context["drill_rows"]
        self.assertEqual([row.question_id for row in one], [self.e3.pk])

    def test_mistakes_are_private(self):
        other = User.objects.create_user("v79_other", password="x")
        self.attempt({self.e2: "D"})
        self.open_page()
        self.client.force_login(other)
        self.assertEqual(self.check(self.e2, "english", "B").status_code, 403)
        self.assertEqual(self.mistake(self.e2, "english").status, StudentMistake.STATUS_OPEN)
        self.assertEqual(self.client.get(reverse("student_mistakes_drill_root")).context["drill_rows"], [])

    def test_bad_payloads(self):
        self.client.force_login(self.kid)
        url = reverse("student_mistake_check_root")
        self.assertEqual(self.client.post(url, "[]", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(url, json.dumps({"section": "x", "question_id": 1}),
                                          content_type="application/json").status_code, 400)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_learn_became_mistakes(self):
        self.client.force_login(self.kid)
        self.assertRedirects(self.client.get("/learn/"), reverse("student_mistakes_root"), fetch_redirect_response=False)
        page = self.client.get(reverse("student_mistakes_root"))
        self.assertContains(page, 'data-nav-key="mistakes"')
        self.assertNotContains(page, 'data-nav-key="learn"')
        self.assertContains(page, "No mistakes yet")

    def test_staff_are_sent_to_their_dashboard(self):
        teacher = User.objects.create_user("v79_teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(reverse("student_mistakes_root")).status_code, 302)

    def test_drill_pages_hand_out_the_csrf_cookie_their_fetch_needs(self):
        from django.conf import settings
        self.attempt({self.e2: "D"})
        self.open_page()
        response = self.client.get(reverse("student_mistakes_drill_root"), {"mode": "all"})
        self.assertIn(settings.CSRF_COOKIE_NAME, response.cookies)

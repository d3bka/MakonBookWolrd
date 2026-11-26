"""V114: Weak topics — where a class makes the most mistakes, by SAT domain and skill."""
import json
import uuid
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.class_weak_topics import class_weak_topics
from apps.sat.models import (
    Classroom, ClassroomMembership, English_Question, Math_Question, QuestionDomain, QuestionType, Test, TestModule,
    TestReview,
)


class WeakTopicsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.teacher = User.objects.create_user("v114_teacher", password="x")
        self.teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.classroom = Classroom.objects.create(teacher=self.teacher, name="SAT Evening")
        self.kids = []
        for n in range(4):
            kid = User.objects.create_user(f"v114_kid{n}", password="x", first_name=f"Kid{n}")
            ClassroomMembership.objects.create(classroom=self.classroom, user=kid, role="student", status="approved")
            self.kids.append(kid)

        algebra = QuestionDomain.objects.create(name="Algebra")
        geometry = QuestionDomain.objects.create(name="Geometry and Trigonometry")
        self.linear = QuestionType.objects.create(name="Linear functions", domain=algebra)
        self.circles = QuestionType.objects.create(name="Circles", domain=geometry)
        self.test = Test.objects.create(name="DAY7", is_available=True)
        # four "Linear functions" questions (hard for the class) and four "Circles" questions (easy)
        self.lin = [Math_Question.objects.create(test=self.test, module="module_1", number=i + 1, question=f"L{i}",
                                                 a="1", b="2", c="3", d="4", answer="A", written=False,
                                                 domain=algebra, type=self.linear) for i in range(4)]
        self.cir = [Math_Question.objects.create(test=self.test, module="module_1", number=i + 5, question=f"C{i}",
                                                 a="1", b="2", c="3", d="4", answer="B", written=False,
                                                 domain=geometry, type=self.circles) for i in range(4)]

    def attempt(self, user, answers, *, test=None, when=None):
        test, attempt_id = test or self.test, uuid.uuid4()
        TestModule.objects.create(test=test, user=user, section="math", module="m1", attempt_id=attempt_id,
                                  answers=json.dumps({"answers": [{"questionID": q.pk, "answer": a} for q, a in answers.items()]}))
        review = TestReview.objects.create(test=test, user=user, key=f"v114-{attempt_id}", attempt_id=attempt_id, score=600)
        if when:
            TestReview.objects.filter(pk=review.pk).update(created_at=when)
        return review

    def class_answers(self):
        # Linear functions: kids 0-2 get every one wrong, kid 3 gets them right. Circles: all right.
        for n, kid in enumerate(self.kids):
            answers = {q: ("A" if n == 3 else "C") for q in self.lin}
            answers.update({q: "B" for q in self.cir})
            self.attempt(kid, answers)

    def test_weakest_skill_first_with_struggling_students(self):
        self.class_answers()
        result = class_weak_topics(self.classroom, "90", use_cache=False)
        self.assertEqual([s["skill"] for s in result["skills"]], ["Linear functions", "Circles"])
        linear = result["skills"][0]
        self.assertEqual((linear["wrong"], linear["answered"], linear["rate"], linear["students"]), (12, 16, 75, 4))
        self.assertEqual(linear["struggling"], ["Kid0", "Kid1", "Kid2"])
        self.assertEqual(result["skills"][1]["rate"], 0)
        self.assertEqual({d["domain"]: d["rate"] for d in result["domains"]},
                         {"Algebra": 75, "Geometry and Trigonometry": 0})
        top = result["top_questions"]
        self.assertEqual(len(top), 4)  # only the Linear functions questions were missed
        self.assertEqual((top[0]["wrong"], top[0]["answered"], top[0]["common_wrong"]), (3, 4, [("C", 3)]))
        self.assertEqual(result["plan"]["steps"][0]["skill"]["skill"], "Linear functions")
        self.assertIn("Re-teach: Linear functions", result["plan_text"])
        self.assertIn("Check on: Kid0, Kid1, Kid2", result["plan_text"])

    def test_skipped_counts_and_only_the_latest_attempt_of_a_test(self):
        kid = self.kids[0]
        self.attempt(kid, {q: "C" for q in self.lin})                       # all wrong
        self.attempt(kid, {q: "A" for q in self.lin[:2]})                   # retake: 2 right, 2 skipped
        result = class_weak_topics(self.classroom, "90", use_cache=False)
        self.assertEqual(result["attempts"], 1)
        few = {s["skill"]: s for s in result["skills_few_answers"]}       # one student: not ranked
        self.assertEqual((few["Linear functions"]["wrong"], few["Linear functions"]["answered"]), (2, 4))
        self.assertEqual(few["Circles"]["wrong"], 4)                       # skipped = wrong

    def test_other_classes_old_attempts_and_non_practice_tests_are_ignored(self):
        outsider = User.objects.create_user("v114_outsider", password="x")
        self.attempt(outsider, {q: "C" for q in self.lin})
        self.attempt(self.kids[0], {q: "C" for q in self.lin}, when=timezone.now() - timedelta(days=120))
        placement = Test.objects.create(name="PLACEMENT", is_available=True, test_type=Test.TYPE_PLACEMENT)
        q = Math_Question.objects.create(test=placement, module="module_1", number=1, question="P", answer="A", type=self.linear)
        self.attempt(self.kids[1], {q: "B"}, test=placement)
        self.assertEqual(class_weak_topics(self.classroom, "90", use_cache=False)["answered"], 0)
        self.assertEqual(class_weak_topics(self.classroom, "all", use_cache=False)["answered"], 8)

    def test_new_attempt_refreshes_the_cached_result(self):
        self.attempt(self.kids[0], {q: "C" for q in self.lin})
        self.assertEqual(class_weak_topics(self.classroom)["attempts"], 1)
        self.attempt(self.kids[1], {q: "C" for q in self.lin})
        self.assertEqual(class_weak_topics(self.classroom)["attempts"], 2)

    def test_teacher_page_shows_plan_and_questions(self):
        self.class_answers()
        self.client.force_login(self.teacher)
        page = self.client.get(reverse("teacher_weak_topics_root"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Plan for the next lesson")
        self.assertContains(page, "Re-teach: Linear functions")
        self.assertContains(page, "DAY7 · Q1")
        self.assertContains(page, "3 of 4 wrong · 75%")
        self.assertContains(page, 'data-nav-key="weak-topics"')

    def test_teacher_sees_only_own_classes(self):
        other_teacher = User.objects.create_user("v114_other", password="x")
        other = Classroom.objects.create(teacher=other_teacher, name="Not mine")
        self.client.force_login(self.teacher)
        page = self.client.get(reverse("teacher_weak_topics_root"), {"classroom": other.pk})
        self.assertEqual(page.context["classroom"], self.classroom)
        self.assertNotContains(page, "Not mine")

    def test_access(self):
        kid = self.kids[0]
        self.client.force_login(kid)
        self.assertEqual(self.client.get(reverse("teacher_weak_topics_root")).status_code, 403)
        self.assertEqual(self.client.get(reverse("manager_weak_topics_root")).status_code, 403)
        manager = User.objects.create_user("v114_manager", password="x")
        manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.client.force_login(manager)
        page = self.client.get(reverse("manager_weak_topics_root"), {"classroom": self.classroom.pk, "period": "30"})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "No practice tests yet")

    def test_english_questions_render_with_the_correct_choice(self):
        info = QuestionDomain.objects.create(name="Craft and Structure")
        words = QuestionType.objects.create(name="Words in Context", domain=info)
        eq = English_Question.objects.create(test=self.test, module="module_1", number=1, question="Which word <b>fits</b>?",
                                             a="big", b="small", c="red", d="old", answer="B",
                                             response_type="multiple_choice", domain=info, type=words)
        for kid in self.kids[:3]:
            attempt_id = uuid.uuid4()
            TestModule.objects.create(test=self.test, user=kid, section="english", module="m1", attempt_id=attempt_id,
                                      answers=json.dumps({"answers": [{"questionID": eq.pk, "answer": "A"}]}))
            TestReview.objects.create(test=self.test, user=kid, key=f"v114e-{attempt_id}", attempt_id=attempt_id, score=500)
        self.client.force_login(self.teacher)
        page = self.client.get(reverse("teacher_weak_topics_root"))
        self.assertContains(page, "Which word &lt;b&gt;fits&lt;/b&gt;?")  # legacy text is escaped
        self.assertContains(page, '<li class="correct"><b>B.</b><span>small</span></li>', html=True)

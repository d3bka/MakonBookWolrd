from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import English_Question, Math_Question, Test, TestModule, TestModuleDraft, TestStage


class AbandonedAttemptTests(TestCase):
    """Coming back to an attempt abandoned without a single answer starts afresh."""

    def setUp(self):
        self.user = User.objects.create_superuser("student_aa", "s@x.uz", "x")
        self.client.force_login(self.user)
        self.test = self.make_test("DAY90")

    def make_test(self, name):
        test = Test.objects.create(name=name, is_available=True)
        English_Question.objects.create(test=test, module="module_1", number=1, question="E", a="a", b="b", c="c", d="d", answer="A")
        Math_Question.objects.create(test=test, module="module_1", number=1, question="M", a="1", b="2", c="3", d="4", answer="B")
        return test

    def open(self, test=None):
        return self.client.get(reverse("practice_test_module_root", kwargs={"pk": (test or self.test).name}) + "?test_mode=full_test")

    def started_stage(self, test=None):
        self.assertEqual(self.open(test).status_code, 200)
        return TestStage.objects.get(user=self.user, test=test or self.test)

    def age(self, stage, *, deadline_ago=timedelta(hours=2), touched_ago=None):
        TestModuleDraft.objects.filter(attempt_id=stage.attempt_id).update(deadline_at=timezone.now() - deadline_ago)
        if touched_ago:
            moment = timezone.now() - touched_ago
            TestModuleDraft.objects.filter(attempt_id=stage.attempt_id).update(updated_at=moment)
            TestStage.objects.filter(pk=stage.pk).update(updated_at=moment, created_at=moment)

    def test_expired_and_unanswered_starts_a_fresh_attempt(self):
        old = self.started_stage()
        self.age(old)
        response = self.open()
        self.assertRedirects(response, reverse("practice_test_module_root", kwargs={"pk": self.test.name}) + "?test_mode=full_test", fetch_redirect_response=False)
        self.assertFalse(TestStage.objects.filter(pk=old.pk).exists())
        self.assertFalse(TestModuleDraft.objects.filter(attempt_id=old.attempt_id).exists())
        fresh = self.open()
        self.assertEqual(fresh.status_code, 200)
        self.assertTemplateUsed(fresh, "test/shared/attempt_eng.html")
        new = TestStage.objects.get(user=self.user, test=self.test)
        self.assertNotEqual(new.attempt_id, old.attempt_id)
        self.assertFalse(TestModule.objects.filter(attempt_id=old.attempt_id).exists())

    def test_an_attempt_with_an_answer_is_never_discarded(self):
        old = self.started_stage()
        draft = TestModuleDraft.objects.get(attempt_id=old.attempt_id)
        draft.answers = [{"questionID": 1, "answer": "A", "time_spent": 10}]
        draft.save(update_fields=["answers"])
        self.age(old)
        self.open()
        self.assertTrue(TestStage.objects.filter(pk=old.pk).exists())
        # The expired module was submitted with the answer, as before.
        self.assertTrue(TestModule.objects.filter(attempt_id=old.attempt_id, section="english").exists())

    def test_a_recent_attempt_is_resumed(self):
        old = self.started_stage()
        self.age(old, deadline_ago=timedelta(minutes=5))  # time just ran out: not abandoned
        self.open()
        self.assertTrue(TestStage.objects.filter(pk=old.pk).exists())

    def test_an_untouched_day_old_attempt_with_time_left_is_also_fresh(self):
        old = self.started_stage()
        self.age(old, deadline_ago=-timedelta(minutes=20), touched_ago=timedelta(days=3))
        self.open()
        self.assertFalse(TestStage.objects.filter(pk=old.pk).exists())

    def test_an_abandoned_attempt_on_another_test_does_not_block_this_one(self):
        other = self.make_test("DAY91")
        old = self.started_stage(other)
        self.age(old)
        response = self.open()  # DAY90, while DAY91 is unfinished
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TestStage.objects.filter(pk=old.pk).exists())
        self.assertEqual(self.open().status_code, 200)
        self.assertTrue(TestStage.objects.filter(user=self.user, test=self.test).exists())

"""V69: one TestReview per attempt — DB constraint, race-safe helper, merge migration."""
import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.sat.models import Classroom, Test, TestReview
from apps.sat.views import _get_or_create_attempt_review


class TestReviewUniquenessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("uniq-student", password="x")
        self.teacher = User.objects.create_user("uniq-teacher", password="x")
        self.test = Test.objects.create(name="UNIQ DAY1")
        self.classroom = Classroom.objects.create(teacher=self.teacher, name="Uniq")
        self.attempt = uuid.uuid4()

    def test_db_rejects_second_review_for_same_solo_attempt(self):
        TestReview.objects.create(user=self.user, test=self.test, attempt_id=self.attempt, key="k1"+"x"*90)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TestReview.objects.create(user=self.user, test=self.test, attempt_id=self.attempt, key="k2"+"x"*90)

    def test_db_rejects_second_review_for_same_classroom_attempt(self):
        TestReview.objects.create(user=self.user, test=self.test, attempt_id=self.attempt, classroom=self.classroom, key="k3"+"x"*90)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TestReview.objects.create(user=self.user, test=self.test, attempt_id=self.attempt, classroom=self.classroom, key="k4"+"x"*90)

    def test_same_attempt_in_different_scope_is_allowed(self):
        TestReview.objects.create(user=self.user, test=self.test, attempt_id=self.attempt, key="k5"+"x"*90)
        TestReview.objects.create(user=self.user, test=self.test, attempt_id=self.attempt, classroom=self.classroom, key="k6"+"x"*90)
        self.assertEqual(TestReview.objects.count(), 2)

    def test_retakes_with_new_attempt_ids_are_allowed(self):
        TestReview.objects.create(user=self.user, test=self.test, attempt_id=uuid.uuid4(), key="k7"+"x"*90)
        TestReview.objects.create(user=self.user, test=self.test, attempt_id=uuid.uuid4(), key="k8"+"x"*90)
        self.assertEqual(TestReview.objects.count(), 2)

    def test_helper_reuses_existing_review(self):
        first, created = _get_or_create_attempt_review(self.user, self.test, self.attempt, None)
        second, created_again = _get_or_create_attempt_review(self.user, self.test, self.attempt, None)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(len(first.key), 100)  # share key is set on insert
        self.assertEqual(first.pk, second.pk)

    def test_helper_recovers_when_a_concurrent_request_wins_the_insert(self):
        winner = TestReview.objects.create(user=self.user, test=self.test, attempt_id=self.attempt, key="k9"+"x"*90)
        real_filter = TestReview.objects.filter
        calls = {"n": 0}

        def stale_first_lookup(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:  # the racing request read before the winner committed
                return real_filter(pk=-1)
            return real_filter(*args, **kwargs)

        from unittest.mock import patch
        with patch.object(TestReview.objects, "filter", side_effect=stale_first_lookup):
            review, created = _get_or_create_attempt_review(self.user, self.test, self.attempt, None)
        self.assertFalse(created)
        self.assertEqual(review.pk, winner.pk)
        self.assertEqual(TestReview.objects.count(), 1)


class MergeDuplicateReviewsMigrationTests(TransactionTestCase):
    before = [("sat", "0063_global_event_attempt_run_mode")]
    after = [("sat", "0065_testreview_unique_attempt")]

    def _migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        self._migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())

    def test_duplicates_are_merged_into_the_scored_review(self):
        old_apps = self._migrate(self.before)
        UserM = old_apps.get_model("auth", "User")
        TestM = old_apps.get_model("sat", "Test")
        ReviewM = old_apps.get_model("sat", "TestReview")
        ClassroomM = old_apps.get_model("sat", "Classroom")
        AssignmentM = old_apps.get_model("sat", "ClassroomHomeworkAssignment")
        SubmissionM = old_apps.get_model("sat", "ClassroomHomeworkSubmission")

        user = UserM.objects.create(username="dup-student")
        teacher = UserM.objects.create(username="dup-teacher")
        test = TestM.objects.create(name="DUP DAY")
        classroom = ClassroomM.objects.create(teacher=teacher, name="Dup class")
        attempt = uuid.uuid4()
        now = timezone.now()

        unscored = ReviewM.objects.create(user=user, test=test, attempt_id=attempt, classroom=classroom,
                                          key="a" * 100, integrity_violation_count=3)
        scored = ReviewM.objects.create(user=user, test=test, attempt_id=attempt, classroom=classroom,
                                        key="b" * 100, score=1350)
        ReviewM.objects.filter(pk=scored.pk).update(created_at=now + timedelta(minutes=1))
        other_attempt = ReviewM.objects.create(user=user, test=test, attempt_id=uuid.uuid4(), score=1200, key="c" * 100)

        assignment = AssignmentM.objects.create(classroom=classroom, created_by=teacher, title="HW", test=test,
                                                assignment_type="test", assign_all=True)
        submission = SubmissionM.objects.create(assignment=assignment, student=user, test_review=unscored)

        new_apps = self._migrate(self.after)
        ReviewN = new_apps.get_model("sat", "TestReview")
        SubmissionN = new_apps.get_model("sat", "ClassroomHomeworkSubmission")

        remaining = ReviewN.objects.filter(attempt_id=attempt)
        self.assertEqual(remaining.count(), 1)
        keeper = remaining.get()
        self.assertEqual(keeper.pk, scored.pk)
        self.assertEqual(keeper.score, 1350)
        self.assertEqual(keeper.integrity_violation_count, 3)  # folded in from the duplicate
        self.assertEqual(SubmissionN.objects.get(pk=submission.pk).test_review_id, scored.pk)
        self.assertTrue(ReviewN.objects.filter(pk=other_attempt.pk).exists())

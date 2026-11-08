import json
import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom,
    ClassroomMembership,
    Math_Question,
    StudentPracticeTestAccess,
    StudentSectionAccess,
    Test,
    TestModule,
    TestReview,
    TestStage,
)
from apps.sat.views import _build_unified_attempt_history, _snapshot_review_attempt_metadata


class AttemptHistoryV551Tests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username='history_teacher_v551', password='pass')
        self.student = User.objects.create_user(username='history_student_v551', password='pass')
        self.classroom = Classroom.objects.create(teacher=self.teacher, name='History V551')
        self.membership = ClassroomMembership.objects.create(
            classroom=self.classroom,
            user=self.student,
            role='student',
            status='approved',
            approved_at=timezone.now(),
        )
        StudentSectionAccess.objects.create(
            membership=self.membership,
            section='practice_tests',
            has_access=True,
        )

        self.day1 = Test.objects.create(name='HISTORY DAY1', is_available=True)
        self.day2 = Test.objects.create(name='HISTORY DAY2', is_available=True)
        StudentPracticeTestAccess.objects.create(membership=self.membership, test=self.day1, has_access=True)
        StudentPracticeTestAccess.objects.create(membership=self.membership, test=self.day2, has_access=True)

        Math_Question.objects.create(
            test=self.day1,
            module='module_1',
            number=1,
            question='1 + 0 = ?',
            answer='1',
            written=True,
        )
        Math_Question.objects.create(
            test=self.day2,
            module='module_1',
            number=1,
            question='2 + 0 = ?',
            answer='2',
            written=True,
        )
        self.client.force_login(self.student)

    def _review(self, test, score, *, classroom=None, attempt_id=None, key=None):
        return TestReview.objects.create(
            user=self.student,
            test=test,
            classroom=classroom,
            test_type='regular',
            attempt_id=attempt_id or uuid.uuid4(),
            score=score,
            key=key or f'history-{uuid.uuid4().hex}',
        )

    def test_available_library_does_not_duplicate_completed_test(self):
        self._review(self.day1, 600)
        response = self.client.get(reverse('practice_tests_root'))
        self.assertEqual(response.status_code, 200)
        names = [test.name for test in response.context['available_tests']]
        self.assertEqual(names.count(self.day1.name), 1)
        self.assertEqual(set(names), {self.day1.name, self.day2.name})
        self.assertEqual(response.context['practice_summary']['history'], 1)

    def test_history_contains_each_completed_attempt_not_just_latest_test(self):
        self._review(self.day1, 540)
        self._review(self.day1, 620)
        history = _build_unified_attempt_history(self.student)
        self.assertEqual(len(history), 2)
        self.assertEqual([item['score'] for item in history], [620, 540])
        self.assertEqual([item['attempt_number'] for item in history], [2, 1])

    def test_history_survives_when_current_test_access_is_removed(self):
        self._review(self.day1, 610)
        StudentPracticeTestAccess.objects.filter(membership=self.membership, test=self.day1).update(has_access=False)
        response = self.client.get(reverse('practice_tests_root'))
        self.assertEqual(response.status_code, 200)
        available_names = [test.name for test in response.context['available_tests']]
        history_names = [item['name'] for item in response.context['history_attempts']]
        self.assertNotIn(self.day1.name, available_names)
        self.assertIn(self.day1.name, history_names)

    def test_in_progress_is_separate_from_available(self):
        TestStage.objects.create(
            user=self.student,
            test=self.day2,
            test_type='regular',
            stage=1,
            mode='single_math_m1',
            integrity_mode='off',
            integrity_fullscreen_required=False,
        )
        response = self.client.get(reverse('practice_tests_root'))
        available = [test.name for test in response.context['available_tests']]
        in_progress = [test.name for test in response.context['in_progress_tests']]
        self.assertIn(self.day2.name, available)
        self.assertEqual(in_progress, [self.day2.name])
        self.assertEqual(response.context['practice_summary']['in_progress'], 1)

    def test_history_infers_mode_from_immutable_modules_when_stage_is_gone(self):
        attempt_id = uuid.uuid4()
        review = self._review(self.day1, 590, attempt_id=attempt_id)
        TestModule.objects.create(
            user=self.student,
            test=self.day1,
            section='math',
            module='m1',
            test_type='regular',
            attempt_id=attempt_id,
            answers=json.dumps({'answers': []}),
        )
        TestModule.objects.create(
            user=self.student,
            test=self.day1,
            section='math',
            module='m2',
            test_type='regular',
            attempt_id=attempt_id,
            answers=json.dumps({'answers': []}),
        )
        self.assertFalse(TestStage.objects.filter(attempt_id=attempt_id).exists())
        item = next(row for row in _build_unified_attempt_history(self.student) if row['review'].pk == review.pk)
        self.assertEqual(item['mode'], 'math_only')
        self.assertEqual(item['mode_label'], 'Math')
        self.assertEqual(item['module_count'], 2)


    def test_review_snapshots_attempt_mode_and_integrity(self):
        attempt_id = uuid.uuid4()
        stage = TestStage.objects.create(
            user=self.student,
            test=self.day1,
            test_type='regular',
            attempt_id=attempt_id,
            stage=1,
            mode='single_math_m1',
            integrity_mode='strict',
            integrity_violation_count=2,
            integrity_fullscreen_required=True,
        )
        review = self._review(self.day1, 600, attempt_id=attempt_id)
        _snapshot_review_attempt_metadata(
            review, self.student, self.day1, attempt_id, classroom=None
        )
        review.refresh_from_db()
        self.assertEqual(review.run_mode, 'single_math_m1')
        self.assertEqual(review.integrity_mode, 'strict')
        self.assertEqual(review.integrity_violation_count, 2)
        self.assertTrue(review.integrity_fullscreen_required)
        self.assertFalse(review.integrity_terminated)

    def test_legacy_classroom_review_uses_canonical_history_url(self):
        attempt_id = uuid.uuid4()
        review = self._review(
            self.day1,
            600,
            classroom=self.classroom,
            attempt_id=attempt_id,
            key='legacy-history-v551',
        )
        TestModule.objects.create(
            user=self.student,
            test=self.day1,
            classroom=self.classroom,
            section='math',
            module='m1',
            test_type='regular',
            attempt_id=attempt_id,
            answers=json.dumps({'answers': [{'questionID': Math_Question.objects.get(test=self.day1).id, 'answer': '1'}]}),
        )
        item = next(row for row in _build_unified_attempt_history(self.student) if row['review'].pk == review.pk)
        self.assertTrue(item['legacy_classroom_attempt'])
        self.assertTrue(item['result_url'].startswith(reverse('practice_test_results_root', args=[self.day1.name])))
        self.assertNotIn('/classrooms/', item['result_url'])
        self.assertNotIn('classroom_id=', item['result_url'])

    def test_full_retake_creates_fresh_stage_and_opens_module(self):
        old_attempt_id = uuid.uuid4()
        old_stage = TestStage.objects.create(
            user=self.student,
            test=self.day1,
            test_type='regular',
            stage=2,
            mode='single_math_m1',
            attempt_id=old_attempt_id,
        )
        self._review(self.day1, 600, attempt_id=old_attempt_id, key='retake-source-v5545')

        response = self.client.post(
            reverse('practice_test_restart_root', args=[self.day1.name]),
            {'confirm_start': '1', 'integrity_mode': 'standard', 'integrity_max_violations': '3', 'integrity_fullscreen_required': '1'},
        )
        self.assertEqual(response.status_code, 302)

        new_stage = TestStage.objects.filter(
            user=self.student,
            test=self.day1,
            classroom__isnull=True,
        ).order_by('-created_at', '-id').first()
        self.assertIsNotNone(new_stage)
        self.assertNotEqual(new_stage.pk, old_stage.pk)
        self.assertNotEqual(new_stage.attempt_id, old_attempt_id)
        self.assertEqual(new_stage.stage, 1)
        self.assertEqual(new_stage.mode, 'full_test')
        self.assertFalse(TestReview.objects.filter(attempt_id=new_stage.attempt_id, score__isnull=False).exists())
        self.assertEqual(
            response.url,
            reverse('practice_test_attempt_module_root', args=[self.day1.name, new_stage.attempt_id]),
        )

        module_response = self.client.get(response.url)
        self.assertEqual(module_response.status_code, 200)
        self.assertTemplateUsed(module_response, 'test/test_math.html')

    def test_full_retake_ignores_completed_stage_with_newer_updated_at(self):
        old_attempt_id = uuid.uuid4()
        old_stage = TestStage.objects.create(
            user=self.student,
            test=self.day1,
            test_type='regular',
            stage=2,
            mode='single_math_m1',
            attempt_id=old_attempt_id,
            attempt_started_at=timezone.now() - timedelta(days=2),
        )
        self._review(self.day1, 600, attempt_id=old_attempt_id, key='retake-stale-order-v5546')

        response = self.client.post(
            reverse('practice_test_restart_root', args=[self.day1.name]),
            {'confirm_start': '1', 'integrity_mode': 'standard', 'integrity_max_violations': '3', 'integrity_fullscreen_required': '1'},
        )
        self.assertEqual(response.status_code, 302)

        new_stage = TestStage.objects.exclude(pk=old_stage.pk).get(
            user=self.student,
            test=self.day1,
            classroom__isnull=True,
        )

        # Simulate an old completed stage being touched by another result/history
        # flow after the retake row was created. Active-attempt selection must not
        # bounce back to that completed row.
        TestStage.objects.filter(pk=old_stage.pk).update(updated_at=timezone.now() + timedelta(minutes=5))

        module_response = self.client.get(
            reverse('practice_test_module_root', args=[self.day1.name])
        )
        self.assertEqual(module_response.status_code, 200)
        self.assertTemplateUsed(module_response, 'test/test_math.html')
        self.assertEqual(module_response.context['attempt_id'], new_stage.attempt_id)

        explicit_response = self.client.get(response.url)
        self.assertEqual(explicit_response.status_code, 200)
        self.assertTemplateUsed(explicit_response, 'test/test_math.html')
        self.assertEqual(explicit_response.context['attempt_id'], new_stage.attempt_id)

        # The generic module URL is also pinned by the browser session, so an
        # old completed stage touched later cannot steal the active retake.
        generic_again = self.client.get(reverse('practice_test_module_root', args=[self.day1.name]))
        self.assertEqual(generic_again.status_code, 200)
        self.assertEqual(generic_again.context['attempt_id'], new_stage.attempt_id)

    def test_full_retake_with_25_completed_attempts_opens_26th_attempt(self):
        # Production can have long history. The count must never behave like an
        # implicit retake limit and completed rows must never win active selection.
        for index in range(25):
            attempt_id = uuid.uuid4()
            TestStage.objects.create(
                user=self.student,
                test=self.day1,
                test_type='regular',
                stage=2,
                mode='single_math_m1',
                attempt_id=attempt_id,
                attempt_started_at=timezone.now() - timedelta(days=30 - index),
            )
            self._review(self.day1, 400 + index, attempt_id=attempt_id)

        response = self.client.post(
            reverse('practice_test_restart_root', args=[self.day1.name]),
            {
                'confirm_start': '1',
                'integrity_mode': 'standard',
                'integrity_max_violations': '3',
                'integrity_fullscreen_required': '1',
            },
        )
        self.assertEqual(response.status_code, 302)

        new_stage = (
            TestStage.objects
            .filter(user=self.student, test=self.day1, classroom__isnull=True)
            .exclude(attempt_id__in=TestReview.objects.filter(
                user=self.student, test=self.day1, score__isnull=False,
            ).values('attempt_id'))
            .get()
        )
        self.assertEqual(
            response.url,
            reverse('practice_test_attempt_module_root', args=[self.day1.name, new_stage.attempt_id]),
        )
        self.assertEqual(
            TestStage.objects.filter(user=self.student, test=self.day1, classroom__isnull=True).count(),
            26,
        )

        module_response = self.client.get(response.url)
        self.assertEqual(module_response.status_code, 200)
        self.assertTemplateUsed(module_response, 'test/test_math.html')
        self.assertEqual(module_response.context['attempt_id'], new_stage.attempt_id)

    def test_canonical_results_can_open_legacy_classroom_history(self):
        attempt_id = uuid.uuid4()
        question = Math_Question.objects.get(test=self.day1)
        review = self._review(
            self.day1,
            600,
            classroom=self.classroom,
            attempt_id=attempt_id,
            key='legacy-open-v551',
        )
        TestModule.objects.create(
            user=self.student,
            test=self.day1,
            classroom=self.classroom,
            section='math',
            module='m1',
            test_type='regular',
            attempt_id=attempt_id,
            answers=json.dumps({'answers': [{'questionID': question.id, 'answer': '1', 'time_spent': 10}]}),
        )
        response = self.client.get(
            reverse('practice_test_results_root', args=[self.day1.name]),
            {'review_key': review.key},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_review'].pk, review.pk)
        self.assertIsNone(response.context['classroom'])

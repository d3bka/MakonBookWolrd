import uuid
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom,
    ClassroomHomeworkAssignment,
    ClassroomHomeworkSubmission,
    ClassroomMembership,
    English_Question,
    Math_Question,
    StudentPracticeTestAccess,
    StudentSectionAccess,
    Test,
    TestModule,
    TestReview,
)
from apps.sat.views import (
    _claim_homework_test_stage,
    _homework_review_matches_assignment,
    _sync_homework_from_scored_review,
)


class HomeworkIntegrationV553Tests(TestCase):
    def setUp(self):
        teacher_group, _ = Group.objects.get_or_create(name='Teacher')
        self.teacher = User.objects.create_user(username='hw_teacher_v553', password='pass')
        self.teacher.groups.add(teacher_group)
        self.student = User.objects.create_user(username='hw_student_v553', password='pass')
        self.classroom = Classroom.objects.create(teacher=self.teacher, name='Math V553')
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
        self.test = Test.objects.create(name='DAY V553', is_available=True)
        StudentPracticeTestAccess.objects.create(
            membership=self.membership,
            test=self.test,
            has_access=True,
        )
        English_Question.objects.create(test=self.test, module='module_1', number=1, question='E1', answer='A')
        English_Question.objects.create(test=self.test, module='module_2', number=1, question='E2', answer='A')
        Math_Question.objects.create(test=self.test, module='module_1', number=1, question='M1', answer='1', written=True)
        Math_Question.objects.create(test=self.test, module='module_2', number=1, question='M2', answer='2', written=True)
        self.assignment = ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom,
            created_by=self.teacher,
            title='DAY Math homework',
            assignment_type=ClassroomHomeworkAssignment.TYPE_TEST,
            test=self.test,
            required_test_mode=ClassroomHomeworkAssignment.TEST_MODE_MATH,
            required_integrity_mode=ClassroomHomeworkAssignment.INTEGRITY_STANDARD,
            assign_all=True,
            due_at=timezone.now() + timedelta(days=2),
        )
        self.client.force_login(self.student)

    def _review(self, *, mode='math_only', integrity='standard', started_at=None):
        attempt_id = uuid.uuid4()
        started_at = started_at or (timezone.now() + timedelta(seconds=1))
        review = TestReview.objects.create(
            user=self.student,
            test=self.test,
            attempt_id=attempt_id,
            score=700,
            run_mode=mode,
            integrity_mode=integrity,
            attempt_started_at=started_at,
        )
        review.update_key()
        TestModule.objects.create(
            user=self.student,
            test=self.test,
            attempt_id=attempt_id,
            section='math',
            module='m1',
            answers='{"answers": []}',
            test_type='regular',
        )
        TestModule.objects.create(
            user=self.student,
            test=self.test,
            attempt_id=attempt_id,
            section='math',
            module='m2',
            answers='{"answers": []}',
            test_type='regular',
        )
        return review

    def test_teacher_can_choose_homework_mode_and_anticheat(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse('teacher_classroom_homework_root', args=[self.classroom.pk]),
            {
                'title': 'Strict math',
                'assignment_type': 'sat_test',
                'test': self.test.pk,
                'required_test_mode': 'math_only',
                'required_integrity_mode': 'strict',
                'assign_all': '1',
                'due_at': (timezone.localtime(timezone.now() + timedelta(days=3))).strftime('%Y-%m-%dT%H:%M'),
            },
        )
        self.assertEqual(response.status_code, 302)
        saved = ClassroomHomeworkAssignment.objects.exclude(pk=self.assignment.pk).get()
        self.assertEqual(saved.required_test_mode, 'math_only')
        self.assertEqual(saved.required_integrity_mode, 'strict')

    def test_homework_launch_is_canonical_and_carries_locked_settings(self):
        self.assignment.required_integrity_mode = 'strict'
        self.assignment.save(update_fields=['required_integrity_mode'])
        response = self.client.get(reverse('student_homework_launch_root', args=[self.assignment.pk]))
        self.assertEqual(response.status_code, 302)
        parsed = urlparse(response.url)
        self.assertEqual(parsed.path, reverse('practice_test_start_root', args=[self.test.name]))
        query = parse_qs(parsed.query)
        self.assertEqual(query['homework'][0], str(self.assignment.pk))
        self.assertEqual(query['test_mode'][0], 'math_only')
        self.assertEqual(query['integrity_mode'][0], 'strict')
        self.assertEqual(query['configured'][0], '1')

    def test_expired_homework_cannot_start_new_attempt(self):
        self.assignment.due_at = timezone.now() - timedelta(seconds=1)
        self.assignment.save(update_fields=['due_at'])
        response = self.client.get(reverse('student_homework_launch_root', args=[self.assignment.pk]))
        self.assertRedirects(response, reverse('student_homework_root'), fetch_redirect_response=False)

    def test_full_strict_attempt_satisfies_math_standard_homework(self):
        review = self._review(mode='full_test', integrity='strict')
        self.assertTrue(_homework_review_matches_assignment(review, self.assignment))

    def test_attempt_started_before_assignment_does_not_satisfy_homework(self):
        review = self._review(
            mode='math_only',
            integrity='standard',
            started_at=self.assignment.created_at - timedelta(minutes=5),
        )
        self.assertFalse(_homework_review_matches_assignment(review, self.assignment))

    def test_ordinary_tests_attempt_becomes_completed_candidate_not_auto_submitted(self):
        review = self._review()
        result = _sync_homework_from_scored_review(self.student, review)
        submission = ClassroomHomeworkSubmission.objects.get(assignment=self.assignment, student=self.student)
        self.assertEqual(submission.status, ClassroomHomeworkSubmission.STATUS_COMPLETED)
        self.assertEqual(submission.source, ClassroomHomeworkSubmission.SOURCE_PRACTICE_TESTS)
        self.assertEqual([row.pk for row in result['candidates']], [self.assignment.pk])
        self.assertEqual(result['auto_submitted'], [])

    def test_homework_launched_attempt_auto_submits(self):
        review = self._review()
        submission = ClassroomHomeworkSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
            status=ClassroomHomeworkSubmission.STATUS_IN_PROGRESS,
            source=ClassroomHomeworkSubmission.SOURCE_HOMEWORK,
            attempt_id=review.attempt_id,
            started_at=timezone.now(),
        )
        result = _sync_homework_from_scored_review(self.student, review)
        submission.refresh_from_db()
        self.assertEqual(submission.status, ClassroomHomeworkSubmission.STATUS_SUBMITTED)
        self.assertEqual(submission.test_review_id, review.pk)
        self.assertEqual([row.pk for row in result['auto_submitted']], [self.assignment.pk])

    def test_one_attempt_can_satisfy_two_assignments(self):
        second = ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom,
            created_by=self.teacher,
            title='DAY M1 homework',
            assignment_type='sat_test',
            test=self.test,
            required_test_mode='single_math_m1',
            required_integrity_mode='off',
            assign_all=True,
            due_at=timezone.now() + timedelta(days=3),
        )
        review = self._review(mode='full_test', integrity='strict')
        result = _sync_homework_from_scored_review(self.student, review)
        self.assertEqual({row.pk for row in result['candidates']}, {self.assignment.pk, second.pk})
        self.assertEqual(
            ClassroomHomeworkSubmission.objects.filter(
                student=self.student,
                status=ClassroomHomeworkSubmission.STATUS_COMPLETED,
            ).count(),
            2,
        )

    def test_submit_endpoint_moves_completed_candidate_to_submitted(self):
        review = self._review()
        _sync_homework_from_scored_review(self.student, review)
        response = self.client.post(
            reverse('student_homework_submit_attempt_root'),
            {'review_key': review.key, 'assignment_ids': [str(self.assignment.pk)]},
        )
        self.assertEqual(response.status_code, 302)
        submission = ClassroomHomeworkSubmission.objects.get(assignment=self.assignment, student=self.student)
        self.assertEqual(submission.status, ClassroomHomeworkSubmission.STATUS_SUBMITTED)
        self.assertIsNotNone(submission.submitted_at)

    def test_submitted_homework_moves_from_todo_to_completed(self):
        review = self._review()
        submission = ClassroomHomeworkSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
            source=ClassroomHomeworkSubmission.SOURCE_PRACTICE_TESTS,
        )
        submission.mark_submitted(test_review=review)

        todo = self.client.get(reverse('student_homework_root'))
        self.assertEqual(todo.status_code, 200)
        self.assertFalse(any(row.pk == self.assignment.pk for row in todo.context['homework_assignments']))
        completed = self.client.get(reverse('student_homework_root'), {'view': 'completed'})
        self.assertEqual(completed.status_code, 200)
        self.assertTrue(any(row.pk == self.assignment.pk for row in completed.context['homework_assignments']))

    def test_homework_claim_creates_locked_stage(self):
        self.assignment.required_integrity_mode = 'strict'
        self.assignment.save(update_fields=['required_integrity_mode'])
        stage, blocked, created = _claim_homework_test_stage(self.student, self.test, self.assignment)
        self.assertTrue(created)
        self.assertIsNone(blocked)
        self.assertEqual(stage.mode, 'math_only')
        self.assertEqual(stage.integrity_mode, 'strict')
        self.assertTrue(stage.integrity_fullscreen_required)
        self.assertIsNotNone(stage.attempt_started_at)

    def test_legacy_staff_create_without_new_policy_fields_defaults_to_off_full(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse('teacher_classroom_homework_root', args=[self.classroom.pk]),
            {
                'title': 'Legacy SAT homework',
                'assignment_type': 'sat_test',
                'test': self.test.pk,
                'assign_all': '1',
                'due_at': (timezone.localtime(timezone.now() + timedelta(days=2))).strftime('%Y-%m-%dT%H:%M'),
            },
        )
        self.assertEqual(response.status_code, 302)
        saved = ClassroomHomeworkAssignment.objects.exclude(pk=self.assignment.pk).get(
            title='Legacy SAT homework'
        )
        self.assertEqual(saved.required_test_mode, ClassroomHomeworkAssignment.TEST_MODE_FULL)
        self.assertEqual(saved.required_integrity_mode, ClassroomHomeworkAssignment.INTEGRITY_OFF)

    def test_legacy_edit_without_new_policy_fields_preserves_existing_policy(self):
        self.assignment.required_test_mode = ClassroomHomeworkAssignment.TEST_MODE_MATH
        self.assignment.required_integrity_mode = ClassroomHomeworkAssignment.INTEGRITY_STRICT
        self.assignment.save(update_fields=['required_test_mode', 'required_integrity_mode'])

        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse('teacher_classroom_homework_root', args=[self.classroom.pk]),
            {
                'action': 'edit',
                'assignment_id': self.assignment.pk,
                'title': 'Edited legacy payload',
                'assignment_type': 'sat_test',
                'test': self.test.pk,
                'preserve_targets': '1',
                'assign_all': '1',
                'due_at': (timezone.localtime(timezone.now() + timedelta(days=2))).strftime('%Y-%m-%dT%H:%M'),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.required_test_mode, ClassroomHomeworkAssignment.TEST_MODE_MATH)
        self.assertEqual(self.assignment.required_integrity_mode, ClassroomHomeworkAssignment.INTEGRITY_STRICT)

    def test_legacy_global_staff_create_accepts_empty_test_without_new_policy_fields(self):
        empty_test = Test.objects.create(name='LEGACY EMPTY V5532', is_available=True)
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse('teacher_homework_root'),
            {
                'action': 'create',
                'submission_token': 'legacy-v5532-token',
                'classroom': str(self.classroom.pk),
                'assignment_type': ClassroomHomeworkAssignment.TYPE_TEST,
                'title': 'Legacy empty SAT homework',
                'instructions': 'Legacy staff payload.',
                'test': empty_test.pk,
                'assign_all': '1',
            },
        )

        self.assertEqual(response.status_code, 302)
        saved = ClassroomHomeworkAssignment.objects.get(title='Legacy empty SAT homework')
        self.assertEqual(saved.required_test_mode, ClassroomHomeworkAssignment.TEST_MODE_FULL)
        self.assertEqual(saved.required_integrity_mode, ClassroomHomeworkAssignment.INTEGRITY_OFF)


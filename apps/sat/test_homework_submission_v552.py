import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom,
    ClassroomHomeworkAssignment,
    ClassroomHomeworkSubmission,
    ClassroomMembership,
    Test,
)
from apps.sat.views import _decorate_homework_submission_state


class HomeworkSubmissionV552Tests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username='hw_teacher_v552', password='pass')
        self.student = User.objects.create_user(username='hw_student_v552', password='pass')
        self.other_student = User.objects.create_user(username='hw_other_v552', password='pass')
        self.classroom = Classroom.objects.create(teacher=self.teacher, name='Homework V552')
        self.membership = ClassroomMembership.objects.create(
            classroom=self.classroom,
            user=self.student,
            role='student',
            status='approved',
            approved_at=timezone.now(),
        )
        ClassroomMembership.objects.create(
            classroom=self.classroom,
            user=self.other_student,
            role='student',
            status='approved',
            approved_at=timezone.now(),
        )
        self.test = Test.objects.create(name='HOMEWORK DAY4', is_available=True)
        self.assignment = ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom,
            created_by=self.teacher,
            title='DAY4 Math homework',
            assignment_type=ClassroomHomeworkAssignment.TYPE_TEST,
            test=self.test,
            assign_all=True,
            due_at=timezone.now() + timedelta(days=2),
        )
        self.client.force_login(self.student)

    def test_missing_submission_means_not_started_without_fanout_row(self):
        self.assertFalse(ClassroomHomeworkSubmission.objects.exists())
        rows = _decorate_homework_submission_state([self.assignment], self.student)
        self.assertEqual(rows[0].student_submission_status, ClassroomHomeworkSubmission.STATUS_NOT_STARTED)
        self.assertIsNone(rows[0].student_submission)
        self.assertFalse(ClassroomHomeworkSubmission.objects.exists())

    def test_opening_homework_lazily_creates_personal_in_progress_submission(self):
        response = self.client.get(reverse('student_homework_launch_root', args=[self.assignment.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('practice_test_start_root', args=[self.test.name])))
        self.assertIn(f'homework={self.assignment.pk}', response.url)
        submission = ClassroomHomeworkSubmission.objects.get(
            assignment=self.assignment,
            student=self.student,
        )
        self.assertEqual(submission.status, ClassroomHomeworkSubmission.STATUS_IN_PROGRESS)
        self.assertEqual(submission.source, ClassroomHomeworkSubmission.SOURCE_HOMEWORK)
        self.assertIsNotNone(submission.started_at)

    def test_submission_is_unique_per_assignment_and_student(self):
        ClassroomHomeworkSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ClassroomHomeworkSubmission.objects.create(
                    assignment=self.assignment,
                    student=self.student,
                )

    def test_two_students_have_independent_submission_state(self):
        first = ClassroomHomeworkSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
        )
        second = ClassroomHomeworkSubmission.objects.create(
            assignment=self.assignment,
            student=self.other_student,
        )
        first.mark_in_progress()
        second.refresh_from_db()
        self.assertEqual(first.status, ClassroomHomeworkSubmission.STATUS_IN_PROGRESS)
        self.assertEqual(second.status, ClassroomHomeworkSubmission.STATUS_NOT_STARTED)

    def test_status_progression_preserves_timestamps_and_submitted_is_terminal(self):
        submission = ClassroomHomeworkSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
        )
        attempt_id = uuid.uuid4()
        submission.mark_in_progress(attempt_id=attempt_id)
        started_at = submission.started_at
        self.assertEqual(submission.attempt_id, attempt_id)

        submission.mark_completed()
        completed_at = submission.completed_at
        self.assertEqual(submission.status, ClassroomHomeworkSubmission.STATUS_COMPLETED)
        self.assertEqual(submission.started_at, started_at)
        self.assertIsNotNone(completed_at)

        submission.mark_submitted()
        submitted_at = submission.submitted_at
        self.assertEqual(submission.status, ClassroomHomeworkSubmission.STATUS_SUBMITTED)
        self.assertEqual(submission.completed_at, completed_at)
        self.assertIsNotNone(submitted_at)

        submission.mark_in_progress()
        submission.refresh_from_db()
        self.assertEqual(submission.status, ClassroomHomeworkSubmission.STATUS_SUBMITTED)
        self.assertEqual(submission.submitted_at, submitted_at)

    def test_homework_page_renders_personal_state_badge(self):
        submission = ClassroomHomeworkSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
        )
        submission.mark_in_progress()
        response = self.client.get(reverse('student_homework_root'))
        self.assertEqual(response.status_code, 200)
        assignment = next(row for row in response.context['homework_assignments'] if row.pk == self.assignment.pk)
        self.assertEqual(assignment.student_submission_status, ClassroomHomeworkSubmission.STATUS_IN_PROGRESS)
        self.assertContains(response, 'In progress')
        self.assertContains(response, 'Continue assignment')

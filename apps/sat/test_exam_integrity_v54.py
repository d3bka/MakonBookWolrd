import json
import uuid

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom,
    ClassroomMembership,
    ClassroomPracticeTestIntegrityPolicy,
    English_Question,
    ExamIntegrityViolation,
    Math_Question,
    StudentPracticeTestAccess,
    StudentSectionAccess,
    Test,
    TestStage,
)
from apps.sat.views import _maybe_schedule_subject_break


class ExamIntegrityV54Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='integrity-user', password='pass')
        self.test = Test.objects.create(name='INTEGRITY54')
        English_Question.objects.create(test=self.test, module='module_1', number=1, question='E1', answer='A')
        English_Question.objects.create(test=self.test, module='module_2', number=1, question='E2', answer='A')
        Math_Question.objects.create(test=self.test, module='module_1', number=1, question='M1', answer='A')
        Math_Question.objects.create(test=self.test, module='module_2', number=1, question='M2', answer='A')
        self.client.force_login(self.user)

    def test_teststage_defaults_to_standard_three_strikes(self):
        stage = TestStage.objects.create(user=self.user, test=self.test, stage=1)
        self.assertEqual(stage.integrity_mode, 'standard')
        self.assertEqual(stage.integrity_max_violations, 3)
        self.assertTrue(stage.integrity_fullscreen_required)

    def test_violation_endpoint_is_idempotent(self):
        stage = TestStage.objects.create(user=self.user, test=self.test, stage=1)
        event_id = str(uuid.uuid4())
        payload = {
            'event_id': event_id,
            'attempt_id': str(stage.attempt_id),
            'event_type': 'tab_hidden',
            'client_occurred_at': timezone.now().isoformat(),
        }
        url = reverse('exam_integrity_violation')
        first = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        second = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        stage.refresh_from_db()
        self.assertEqual(stage.integrity_violation_count, 1)
        self.assertEqual(ExamIntegrityViolation.objects.filter(stage=stage).count(), 1)

    def test_unmonitored_event_does_not_count(self):
        stage = TestStage.objects.create(
            user=self.user,
            test=self.test,
            stage=1,
            integrity_mode='strict',
            integrity_monitored_events=['tab_hidden'],
        )
        response = self.client.post(
            reverse('exam_integrity_violation'),
            data=json.dumps({
                'event_id': str(uuid.uuid4()),
                'attempt_id': str(stage.attempt_id),
                'event_type': 'copy',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ignored'])
        stage.refresh_from_db()
        self.assertEqual(stage.integrity_violation_count, 0)

    def test_third_violation_terminates_attempt(self):
        stage = TestStage.objects.create(user=self.user, test=self.test, stage=1)
        url = reverse('exam_integrity_violation')
        for _idx in range(3):
            response = self.client.post(url, data=json.dumps({
                'event_id': str(uuid.uuid4()),
                'attempt_id': str(stage.attempt_id),
                'event_type': 'tab_hidden',
                'client_occurred_at': timezone.now().isoformat(),
            }), content_type='application/json')
            self.assertEqual(response.status_code, 200)
        stage.refresh_from_db()
        self.assertIsNotNone(stage.integrity_terminated_at)
        self.assertEqual(stage.integrity_violation_count, 3)
        self.assertFalse(stage.integrity_retake_locked)

    def test_subject_change_schedules_break(self):
        stage = TestStage.objects.create(user=self.user, test=self.test, stage=3)
        _maybe_schedule_subject_break(stage, 'english')
        stage.refresh_from_db()
        self.assertIsNotNone(stage.scheduled_break_started_at)
        self.assertIsNotNone(stage.scheduled_break_until)
        self.assertGreater(stage.scheduled_break_until, stage.scheduled_break_started_at)


class ClassroomIntegrityPolicyV54Tests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username='integrity-teacher', password='pass')
        teacher_group, _ = Group.objects.get_or_create(name='Teacher')
        self.teacher.groups.add(teacher_group)
        self.student = User.objects.create_user(username='integrity-student', password='pass')
        self.classroom = Classroom.objects.create(teacher=self.teacher, name='Integrity Class')
        self.membership = ClassroomMembership.objects.create(
            classroom=self.classroom,
            user=self.student,
            role='student',
            status='approved',
        )
        StudentSectionAccess.objects.create(
            membership=self.membership,
            section='practice_tests',
            has_access=True,
        )
        self.test = Test.objects.create(name='INTEGRITY CLASS TEST')
        English_Question.objects.create(test=self.test, module='module_1', number=1, question='E1', answer='A')
        StudentPracticeTestAccess.objects.create(membership=self.membership, test=self.test, has_access=True)

    def test_classroom_policy_can_store_custom_monitored_events(self):
        policy = ClassroomPracticeTestIntegrityPolicy.objects.create(
            classroom=self.classroom,
            test=self.test,
            mode='strict',
            max_violations=2,
            fullscreen_required=True,
            monitored_events=['tab_hidden', 'fullscreen_exit', 'copy'],
        )
        self.assertEqual(policy.max_violations, 2)
        self.assertEqual(policy.monitored_events, ['tab_hidden', 'fullscreen_exit', 'copy'])

    def test_classroom_termination_locks_retake_until_teacher_unlocks(self):
        stage = TestStage.objects.create(
            user=self.student,
            test=self.test,
            classroom=self.classroom,
            stage=1,
            integrity_mode='standard',
            integrity_max_violations=1,
        )
        self.client.force_login(self.student)
        response = self.client.post(
            reverse('exam_integrity_violation'),
            data=json.dumps({
                'event_id': str(uuid.uuid4()),
                'attempt_id': str(stage.attempt_id),
                'event_type': 'tab_hidden',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        stage.refresh_from_db()
        self.assertTrue(stage.integrity_retake_locked)

        self.client.force_login(self.teacher)
        unlock = self.client.post(reverse(
            'classroom_student_integrity_unlock',
            args=[self.classroom.id, self.student.id, self.test.name],
        ))
        self.assertEqual(unlock.status_code, 302)
        stage.refresh_from_db()
        self.assertFalse(stage.integrity_retake_locked)

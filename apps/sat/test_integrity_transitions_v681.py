import json
import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from datetime import timedelta
from django.utils import timezone
from apps.sat.models import English_Question, Math_Question, Test, TestStage, TestModule, ExamIntegrityViolation

User = get_user_model()


class IntegrityTransitionRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='integrity-v681', password='example')
        self.test = Test.objects.create(name='V681-LIVE-RET-TEST')
        English_Question.objects.create(test=self.test, module='module_1', number=1, question='E1', answer='A')
        English_Question.objects.create(test=self.test, module='module_2', number=1, question='E2', answer='A')
        self.stage = TestStage.objects.create(user=self.user, test=self.test, stage=1)
        self.client.force_login(self.user)
        self.url = reverse('exam_integrity_violation')

    def report(self, event):
        return self.client.post(self.url, json.dumps({
            'event_id': str(uuid.uuid4()), 'attempt_id': str(self.stage.attempt_id),
            'event_type': event, 'client_occurred_at': timezone.now().isoformat(),
        }), content_type='application/json')

    def test_short_blur_cluster_does_not_create_multiple_strikes(self):
        a = self.report('tab_hidden')
        b = self.report('window_blur')
        self.assertEqual(a.status_code, 200)
        self.assertEqual(b.status_code, 200)
        self.assertTrue(b.json()['ignored'])
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.integrity_violation_count, 1)

    def test_last_module_submitted_does_not_accept_late_violation(self):
        self.stage.stage = 3
        self.stage.save(update_fields=['stage'])
        result = self.report('tab_hidden')
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()['ignored'])
        self.assertEqual(ExamIntegrityViolation.objects.filter(stage=self.stage).count(), 0)

    def test_already_submitted_current_module_ignores_late_strike(self):
        TestModule.objects.create(user=self.user, test=self.test, section='english',
            module='m1', test_type='regular', attempt_id=self.stage.attempt_id, answers='{}')
        result = self.report('tab_hidden')
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()['ignored'])
        self.assertEqual(ExamIntegrityViolation.objects.filter(stage=self.stage).count(), 0)

    def test_real_second_strike_after_episode_is_still_counted(self):
        first = self.report('tab_hidden')
        self.assertEqual(first.status_code, 200)
        ExamIntegrityViolation.objects.filter(stage=self.stage).update(
            created_at=timezone.now()-timedelta(seconds=10))
        second = self.report('tab_hidden')
        self.assertFalse(second.json().get('ignored',False))
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.integrity_violation_count, 2)

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.apclasses.models import APExamAttempt, APExamEvent, APMockExam
from apps.apclasses.views import _ap_part_remaining_seconds, _attempts_for_request


class APAttemptReliabilityV5604Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='student-v5604', password='pass-12345')
        self.exam = APMockExam.objects.create(
            title='AP reliability test',
            status='published',
            part_a_duration_minutes=60,
            part_b_duration_minutes=45,
            frq_duration_minutes=30,
        )
        self.event = APExamEvent.objects.create(
            title='AP reliability event',
            exam=self.exam,
            status='live',
            is_public=True,
            is_global=True,
            always_live=True,
            allow_guest_attempts=True,
        )
        self.factory = RequestFactory()

    def test_authenticated_user_is_not_reclassified_by_stale_guest_mode(self):
        own = APExamAttempt.objects.create(event=self.event, student=self.user)
        APExamAttempt.objects.create(
            event=self.event,
            student=None,
            guest_session_key='session:legacy',
            guest_name='Legacy guest',
        )
        request = self.factory.get('/')
        request.user = self.user
        request.session = {'guest_mode': True, 'guest_id': 'legacy'}
        self.assertEqual(list(_attempts_for_request(request, self.event)), [own])

    def test_server_side_part_timer_expires_from_database_timestamp(self):
        attempt = APExamAttempt.objects.create(
            event=self.event,
            student=self.user,
            part_a_started_at=timezone.now() - timedelta(minutes=61),
        )
        self.assertEqual(_ap_part_remaining_seconds(attempt, 'part_a'), 0)

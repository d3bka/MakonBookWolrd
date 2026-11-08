"""V62: no duplicate 21:00 teacher reminders and no messages on free days."""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone

from apps.sat.models import Classroom, ClassroomMembership, MakonNotification
from .assessment_policy import prepare_today_obligations, send_teacher_evening_reminders
from .models import (
    AssessmentCalendarException, AssessmentSchedule, RatingAssessment,
    TeacherAssessmentReminder,
)


class TeacherEveningReminderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user('v62_remind_teacher', password='testpass')
        cls.teacher.groups.add(Group.objects.get_or_create(name='Teacher')[0])
        cls.student = User.objects.create_user('v62_remind_student', password='testpass')
        cls.classroom = Classroom.objects.create(teacher=cls.teacher, name='V62 evening reminder')
        membership = ClassroomMembership.objects.create(
            classroom=cls.classroom, user=cls.student,
            role='student', status='approved',
        )
        ClassroomMembership.objects.filter(pk=membership.pk).update(
            approved_at=timezone.now() - timedelta(days=15),
        )

    def setUp(self):
        self.day = timezone.localdate()
        self.schedule = AssessmentSchedule.objects.create(
            classroom=self.classroom, teacher=self.teacher, starts_on=self.day,
            weekdays=[self.day.isoweekday()], approved_by=self.teacher,
        )
        tz = ZoneInfo('Asia/Tashkent')
        self.early = datetime(self.day.year, self.day.month, self.day.day, 20, 59, tzinfo=tz)
        self.evening = datetime(self.day.year, self.day.month, self.day.day, 21, 0, tzinfo=tz)

    def test_remind_once_at_2100_not_before(self):
        with patch('django.utils.timezone.now', return_value=self.early):
            self.assertEqual(send_teacher_evening_reminders(now=self.early), 0)
        with patch('django.utils.timezone.now', return_value=self.evening):
            self.assertEqual(send_teacher_evening_reminders(now=self.evening), 1)
            self.assertEqual(send_teacher_evening_reminders(now=self.evening), 0)
        self.assertEqual(TeacherAssessmentReminder.objects.filter(teacher=self.teacher).count(), 1)
        notice = MakonNotification.objects.get(user=self.teacher, type=MakonNotification.TYPE_ASSESSMENT)
        self.assertIn('23:59:59', notice.message)
        self.assertEqual(notice.url, '/teacher/assessments/')

    def test_no_reminder_when_assessment_completed(self):
        with patch('django.utils.timezone.now', return_value=self.evening):
            prepare_today_obligations(schedule=self.schedule)
        RatingAssessment.objects.create(
            classroom=self.classroom, teacher=self.teacher, student=self.student,
            lesson_date=self.day, assessed_at=timezone.now(),
            homework=8, progress=8, activity=8, attendance=8, behavior=8,
        )
        with patch('django.utils.timezone.now', return_value=self.evening):
            self.assertEqual(send_teacher_evening_reminders(now=self.evening), 0)
        self.assertFalse(TeacherAssessmentReminder.objects.exists())

    def test_cancelled_lesson_no_reminder(self):
        prepare_today_obligations(schedule=self.schedule)
        AssessmentCalendarException.objects.create(
            schedule=self.schedule, date=self.day, action='cancelled', reason='School closed',
        )
        with patch('django.utils.timezone.now', return_value=self.evening):
            self.assertEqual(send_teacher_evening_reminders(now=self.evening), 0)
        self.assertFalse(MakonNotification.objects.filter(user=self.teacher, type=MakonNotification.TYPE_ASSESSMENT).exists())

    def test_no_reminder_on_nonlesson_day(self):
        self.schedule.weekdays = [self.day.isoweekday() % 7 + 1]
        self.schedule.save(update_fields=['weekdays'])
        with patch('django.utils.timezone.now', return_value=self.evening):
            self.assertEqual(send_teacher_evening_reminders(now=self.evening), 0)

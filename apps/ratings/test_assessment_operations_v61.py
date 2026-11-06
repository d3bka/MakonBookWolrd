"""V61 regression: class-day deadline, per-student fines, manager visibility."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from apps.sat.models import Classroom, ClassroomMembership, MakonNotification
from .assessment_policy import (
    required_lesson_dates, prepare_today_obligations,
    settle_missed_assessments, send_daily_manager_report,
)
from .models import (
    AssessmentCalendarException, AssessmentDailyReport,
    AssessmentObligation, AssessmentPenalty, AssessmentSchedule, RatingAssessment, UserActivityDay,
)


class AssessmentOperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user('v61_teacher', password='testpass')
        cls.manager = User.objects.create_user('v61_manager', password='testpass')
        cls.students = [User.objects.create_user(f'v61_student_{i}', password='testpass') for i in range(2)]
        cls.teacher.groups.add(Group.objects.get_or_create(name='Teacher')[0])
        cls.manager.groups.add(Group.objects.get_or_create(name='Manager')[0])
        cls.classroom = Classroom.objects.create(teacher=cls.teacher, name='V61 SAT')
        for student in cls.students:
            m = ClassroomMembership.objects.create(classroom=cls.classroom, user=student, role='student', status='approved')
            ClassroomMembership.objects.filter(pk=m.pk).update(approved_at=timezone.now() - timedelta(days=4))

    def setUp(self):
        self.today = timezone.localdate()
        self.schedule = AssessmentSchedule.objects.create(
            classroom=self.classroom, teacher=self.teacher,
            starts_on=self.today, weekdays=[self.today.isoweekday()],
            approved_by=self.manager,
        )

    def payload(self):
        return dict(homework='8', progress='8', activity='8', attendance='8', behavior='8', comment='Normal')

    def test_assessment_denied_without_schedule_for_today(self):
        self.schedule.weekdays = [self.today.isoweekday() % 7 + 1]
        self.schedule.save(update_fields=['weekdays'])
        self.client.force_login(self.teacher)
        endpoint = reverse('rating_assess_student', args=[self.classroom.id, self.students[0].id])
        self.assertEqual(self.client.post(endpoint, self.payload()).status_code, 403)
        self.assertEqual(RatingAssessment.objects.count(), 0)

    def test_saves_one_assessment_per_student_lesson_date(self):
        self.client.force_login(self.teacher)
        endpoint = reverse('rating_assess_student', args=[self.classroom.id, self.students[0].id])
        self.assertEqual(self.client.post(endpoint, self.payload()).status_code, 302)
        self.assertEqual(self.client.post(endpoint, self.payload()).status_code, 302)
        self.assertEqual(RatingAssessment.objects.filter(lesson_date=self.today).count(), 1)

    def test_fines_only_for_missing_student_and_idempotent(self):
        self.assertEqual(prepare_today_obligations(schedule=self.schedule), 2)
        self.assertEqual(prepare_today_obligations(schedule=self.schedule), 0)
        RatingAssessment.objects.create(
            classroom=self.classroom, teacher=self.teacher, student=self.students[0],
            lesson_date=self.today, assessed_at=timezone.now(),
            homework=8, progress=8, activity=8, attendance=8, behavior=8,
        )
        fines = settle_missed_assessments(cutoff=self.today + timedelta(days=1))
        self.assertEqual(len(fines), 1)
        self.assertEqual(fines[0].obligation.student, self.students[1])
        self.assertEqual(fines[0].amount_uzs, 5000)
        self.assertEqual(settle_missed_assessments(cutoff=self.today + timedelta(days=1)), [])

    def test_cancelled_lesson_not_fined(self):
        prepare_today_obligations(schedule=self.schedule)
        AssessmentCalendarException.objects.create(schedule=self.schedule, date=self.today, action='cancelled')
        self.assertEqual(settle_missed_assessments(cutoff=self.today + timedelta(days=1)), [])

    def test_second_weekday_not_assessable_today(self):
        self.schedule.weekdays = [self.today.isoweekday() % 7 + 1]
        self.schedule.save(update_fields=['weekdays'])
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('rating_teacher_classroom', args=[self.classroom.pk]))
        self.assertContains(response, 'Assessment locked today')

    def test_midnight_ends_submission_window(self):
        self.client.force_login(self.teacher)
        endpoint = reverse('rating_assess_student', args=[self.classroom.id, self.students[0].id])
        before_midnight = datetime.combine(self.today, time(23, 59, 59), ZoneInfo('Asia/Tashkent'))
        with patch('django.utils.timezone.now', return_value=before_midnight):
            response = self.client.post(endpoint, self.payload())
        self.assertEqual(response.status_code, 302)
        after_midnight = datetime.combine(self.today + timedelta(days=1), time(0, 0, 0), ZoneInfo('Asia/Tashkent'))
        with patch('django.utils.timezone.now', return_value=after_midnight):
            response = self.client.post(endpoint, self.payload())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(RatingAssessment.objects.count(), 1)

    def test_manager_excel_and_student_forbidden(self):
        self.assertEqual(prepare_today_obligations(schedule=self.schedule), 2)
        settle_missed_assessments(cutoff=self.today + timedelta(days=1))
        self.client.force_login(self.students[0])
        self.assertEqual(self.client.get(reverse('manager_penalties_xlsx')).status_code, 403)
        self.client.force_login(self.manager)
        response = self.client.get(reverse('manager_penalties_xlsx') + '?month=' + self.today.strftime('%Y-%m'))
        self.assertEqual(response.status_code, 200)
        book = load_workbook(BytesIO(response.content), read_only=True)
        self.assertIn('By Teacher', book.sheetnames)
        self.assertEqual(book['Per Student'].max_row, 3)

    def test_activity_unique_user_windows(self):
        UserActivityDay.objects.create(user=self.students[0], date=self.today)
        UserActivityDay.objects.create(user=self.students[0], date=self.today - timedelta(days=5))
        UserActivityDay.objects.create(user=self.students[1], date=self.today - timedelta(days=20))
        self.client.force_login(self.manager)
        response = self.client.get(reverse('manager_activity_report'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['today_count'], 1)
        self.assertEqual(response.context['count_15'], 1)
        self.assertEqual(response.context['count_30'], 2)

    def test_waiver_requires_manager_reason(self):
        prepare_today_obligations(schedule=self.schedule)
        fine = settle_missed_assessments(cutoff=self.today + timedelta(days=1))[0]
        self.client.force_login(self.manager)
        url = reverse('manager_review_penalty', args=[fine.pk])
        self.client.post(url, {'status': 'waived', 'note': ''})
        fine.refresh_from_db()
        self.assertEqual(fine.status, 'open')
        self.client.post(url, {'status': 'waived', 'note': 'Cancelled with approval'})
        fine.refresh_from_db()
        self.assertEqual(fine.status, 'waived')

    def test_daily_report_dedup(self):
        yesterday = self.today - timedelta(days=1)
        AssessmentObligation.objects.create(schedule=self.schedule, student=self.students[0], lesson_date=yesterday)
        settle_missed_assessments(cutoff=self.today)
        self.assertTrue(send_daily_manager_report(report_date=yesterday))
        self.assertFalse(send_daily_manager_report(report_date=yesterday))
        self.assertEqual(AssessmentDailyReport.objects.filter(date=yesterday).count(), 1)
        self.assertEqual(MakonNotification.objects.filter(user=self.manager, title__startswith='Assessment report').count(), 1)

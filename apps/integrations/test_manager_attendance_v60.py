"""Access control, absence ordering and declining-attendance signals."""
from datetime import date
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from apps.integrations.models import HollihopAttendance
from apps.sat.models import Classroom


class ManagerAttendanceV60Tests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username='m60', password='xx')
        self.manager.groups.add(Group.objects.get_or_create(name='Manager')[0])
        self.student = User.objects.create_user(username='s60', password='xx')
        self.teacher = User.objects.create_user(username='t60', password='xx')
        self.classroom = Classroom.objects.create(name='Insight classroom', teacher=self.teacher)
        for day, status in [(1,'present'),(3,'present'),(15,'absent'),(18,'absent')]:
            HollihopAttendance.objects.create(student=self.student, classroom=self.classroom, status=status, date=date(2026,10,day), external_key=f'm60-{day}')
        self.url = reverse('manager_attendance_insights') + '?from=2026-10-01&to=2026-10-20'

    def test_only_managers(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 's60')
        self.assertContains(response, '↓ -100.0 pp')

    def test_declining_filter(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url+'&trend=declining')
        self.assertContains(response, 's60')
        self.assertEqual(response.context['matched_students'], 1)

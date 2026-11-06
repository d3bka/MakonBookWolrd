"""Regression tests for protected parent records and student-controlled sharing."""
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.integrations.models import HollihopAttendance
from apps.ratings.models import RatingProfile, TermGrade
from apps.sat.models import Classroom, Test, TestReview


class ParentPrivateV60Tests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='family_student_60', password='pass12345')
        self.student.profile.phone_number = '+998901231234'
        self.student.profile.save(update_fields=['phone_number'])
        self.other_student = User.objects.create_user(username='family_other_60', password='pass12345')
        self.other_student.profile.phone_number = '+998909991234'
        self.other_student.profile.save(update_fields=['phone_number'])
        self.teacher = User.objects.create_user(username='family_teacher_60', password='pass12345')
        self.classroom = Classroom.objects.create(teacher=self.teacher, name='Family Math 60')
        self.profile, _ = RatingProfile.objects.get_or_create(user=self.student)
        TermGrade.objects.create(student=self.student, classroom=self.classroom, academic_year='2026/2027', term='midterm', score=Decimal('87.50'))
        Test.objects.create(name='Family SAT 60')
        TestReview.objects.create(user=self.student, test_id='Family SAT 60', score=1420, key='family-review-60')
        HollihopAttendance.objects.create(student=self.student, classroom=self.classroom, date='2026-10-01', status='absent', external_key='family-hollihop-60')
        self.url = reverse('rating_parent_lookup')

    def test_phone_only_never_exposes_sensitive_academic_records(self):
        self.client.post(self.url, {'action':'lookup', 'phone_number':'+998901231234'})
        response = self.client.get(self.url)
        self.assertContains(response, 'Unlock detailed progress')
        self.assertNotContains(response, '1420')
        self.assertNotContains(response, '87.50')
        self.assertNotContains(response, 'Family SAT 60')

    def test_code_unblocks_only_matching_student_and_switch_revokes(self):
        self.client.post(self.url, {'action':'lookup','phone_number':'+998901231234'})
        bad = self.client.post(self.url, {'action':'verify_private','family_code':'WRONGCODE'})
        self.assertContains(bad, 'Invalid family access code')
        self.assertNotContains(bad, 'Family SAT 60')
        response = self.client.post(self.url, {'action':'verify_private','family_code':self.profile.parent_access_code})
        self.assertEqual(response.status_code, 302)
        page = self.client.get(self.url)
        self.assertContains(page, 'Family SAT 60')
        self.assertContains(page, '1420')
        self.assertContains(page, '87.50')
        self.assertContains(page, 'Hollihop attendance')
        self.client.post(self.url, {'action':'switch'})
        self.assertNotIn('rating_parent_private_student_id', self.client.session)

    def test_parent_code_not_public_and_student_can_retrieve_own(self):
        page = self.client.get(reverse('rating_parent_share_code'))
        self.assertEqual(page.status_code, 302)
        self.client.force_login(self.student)
        page = self.client.get(reverse('rating_parent_share_code'))
        self.assertContains(page, self.profile.parent_access_code)
        self.client.force_login(self.other_student)
        other_page = self.client.get(reverse('rating_parent_share_code'))
        self.assertNotContains(other_page, self.profile.parent_access_code)

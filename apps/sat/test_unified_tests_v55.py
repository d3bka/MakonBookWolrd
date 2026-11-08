from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom,
    ClassroomMembership,
    ClassroomPracticeTestIntegrityPolicy,
    English_Question,
    Math_Question,
    StudentPracticeTestAccess,
    StudentSectionAccess,
    Test,
    TestStage,
)


class UnifiedTestsV55Stage1Tests(TestCase):
    def setUp(self):
        teacher_group, _ = Group.objects.get_or_create(name='Teacher')
        self.math_teacher = User.objects.create_user(username='math_teacher_v55', password='pass')
        self.english_teacher = User.objects.create_user(username='english_teacher_v55', password='pass')
        self.math_teacher.groups.add(teacher_group)
        self.english_teacher.groups.add(teacher_group)
        self.student = User.objects.create_user(username='student_v55', password='pass')

        self.math_class = Classroom.objects.create(teacher=self.math_teacher, name='Math V55')
        self.english_class = Classroom.objects.create(teacher=self.english_teacher, name='English V55')
        self.math_membership = ClassroomMembership.objects.create(
            classroom=self.math_class,
            user=self.student,
            role='student',
            status='approved',
            approved_at=timezone.now(),
        )
        self.english_membership = ClassroomMembership.objects.create(
            classroom=self.english_class,
            user=self.student,
            role='student',
            status='approved',
            approved_at=timezone.now(),
        )
        for membership in (self.math_membership, self.english_membership):
            StudentSectionAccess.objects.create(
                membership=membership,
                section='practice_tests',
                has_access=True,
            )

        self.day57 = Test.objects.create(name='DAY57', is_available=True)
        self.day58 = Test.objects.create(name='DAY58', is_available=True)
        self.day59 = Test.objects.create(name='DAY59', is_available=True)

        # Math: DAY58, DAY59. English: DAY57, DAY58.
        StudentPracticeTestAccess.objects.create(membership=self.math_membership, test=self.day58, has_access=True)
        StudentPracticeTestAccess.objects.create(membership=self.math_membership, test=self.day59, has_access=True)
        StudentPracticeTestAccess.objects.create(membership=self.english_membership, test=self.day57, has_access=True)
        StudentPracticeTestAccess.objects.create(membership=self.english_membership, test=self.day58, has_access=True)

        # A real two-module Math section for runner/integrity tests.
        Math_Question.objects.create(test=self.day58, module='module_1', number=1, question='M1', answer='1', written=True)
        Math_Question.objects.create(test=self.day58, module='module_2', number=1, question='M2', answer='2', written=True)
        # Give DAY57/DAY59 at least one module so cards have meaningful stats.
        English_Question.objects.create(test=self.day57, module='module_1', number=1, question='E57', answer='A')
        Math_Question.objects.create(test=self.day59, module='module_1', number=1, question='M59', answer='1', written=True)

        self.client.force_login(self.student)

    def test_tests_library_is_union_and_deduplicates_same_test(self):
        response = self.client.get(reverse('practice_tests_root'))
        self.assertEqual(response.status_code, 200)
        tests = list(response.context['available_tests'])
        names = [test.name for test in tests]
        self.assertEqual(names, ['DAY57', 'DAY58', 'DAY59'])
        self.assertEqual(names.count('DAY58'), 1)
        self.assertEqual(response.context['practice_summary']['available'], 3)

    def test_student_test_cards_use_only_canonical_tests_urls(self):
        response = self.client.get(reverse('practice_tests_root'))
        html = response.content.decode('utf-8')
        self.assertIn(reverse('practice_test_start_root', args=[self.day58.name]), html)
        self.assertNotIn(f'/classrooms/{self.math_class.id}/tests/', html)
        self.assertNotIn(f'/classrooms/{self.english_class.id}/tests/', html)

    def test_legacy_classroom_start_redirects_to_canonical_start(self):
        response = self.client.get(
            reverse('student_classroom_test_start_root', args=[self.math_class.id, self.day58.name])
        )
        self.assertRedirects(
            response,
            reverse('practice_test_start_root', args=[self.day58.name]),
            fetch_redirect_response=False,
        )

    def test_normal_tests_are_not_locked_to_classroom_integrity(self):
        ClassroomPracticeTestIntegrityPolicy.objects.create(
            classroom=self.math_class,
            test=self.day58,
            mode='strict',
            max_violations=2,
            fullscreen_required=True,
        )
        response = self.client.get(reverse('practice_tests_root'))
        day58 = next(test for test in response.context['active_tests'] if test.name == 'DAY58')
        self.assertFalse(day58.preconfig_integrity_locked)
        self.assertEqual(day58.preconfig_integrity_mode, '')

    def test_canonical_runner_creates_global_attempt_and_respects_off(self):
        response = self.client.get(
            reverse('practice_test_module_root', args=[self.day58.name]),
            {
                'test_mode': 'math_only',
                'integrity_mode': 'off',
                'integrity_fullscreen_required': '0',
            },
        )
        self.assertEqual(response.status_code, 200)
        stage = TestStage.objects.get(user=self.student, test=self.day58, test_type='regular')
        self.assertIsNone(stage.classroom_id)
        self.assertEqual(stage.mode, 'math_only')
        self.assertEqual(stage.integrity_mode, 'off')
        self.assertFalse(stage.integrity_fullscreen_required)

    def test_unfinished_legacy_classroom_attempt_is_adopted_by_unified_runner(self):
        stage = TestStage.objects.create(
            user=self.student,
            test=self.day58,
            classroom=self.math_class,
            stage=1,
            test_type='regular',
            mode='math_only',
            integrity_mode='off',
            integrity_fullscreen_required=False,
        )
        response = self.client.get(reverse('practice_test_start_root', args=[self.day58.name]))
        self.assertRedirects(
            response,
            reverse('practice_test_attempt_module_root', args=[self.day58.name, stage.attempt_id]),
            fetch_redirect_response=False,
        )
        stage.refresh_from_db()
        self.assertIsNone(stage.classroom_id)
        self.assertEqual(stage.integrity_mode, 'off')

    def test_teacher_classroom_summary_still_exists_as_management_surface(self):
        teacher = User.objects.create_user(username='teacher-summary-v55', password='pass')
        teacher_group, _ = Group.objects.get_or_create(name='Teacher')
        teacher.groups.add(teacher_group)
        classroom = Classroom.objects.create(teacher=teacher, name='Management Summary')
        self.client.force_login(teacher)
        response = self.client.get(
            reverse('classroom_practice_tests', kwargs={'classroom_id': classroom.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_student_classroom_library_url_redirects_to_unified_tests(self):
        classroom = Classroom.objects.create(teacher=self.math_teacher, name='Legacy Student Library')
        membership = ClassroomMembership.objects.create(
            classroom=classroom,
            user=self.student,
            role='student',
            status='approved',
            approved_at=timezone.now(),
        )
        StudentSectionAccess.objects.update_or_create(
            membership=membership,
            section='practice_tests',
            defaults={'has_access': True},
        )
        self.client.force_login(self.student)
        response = self.client.get(
            reverse('classroom_practice_tests', kwargs={'classroom_id': classroom.id})
        )
        self.assertRedirects(
            response,
            reverse('practice_tests_root'),
            fetch_redirect_response=False,
        )


"""V77: full MakonBook for current SATMakon (Hollihop) students, 5 free practice tests for everyone else,
and no manual classroom join codes."""
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom, ClassroomJoinCode, ClassroomMembership, StudentPracticeTestAccess, StudentSectionAccess, Test,
)
from apps.sat.student_access import is_active_satmakon_student
from apps.sat.views import _v550_unified_accessible_tests


class PracticeAccessTests(TestCase):
    def setUp(self):
        self.tests = [Test.objects.create(name=f"DAY{i}", is_available=True) for i in range(1, 9)]
        self.kid = User.objects.create_user("v77_kid", password="x")
        self.teacher = User.objects.create_user("v77_teacher", password="x")
        self.teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])

    def open_names(self, user):
        return [t.name for t in _v550_unified_accessible_tests(User.objects.get(pk=user.pk))]

    def make_active_by_status(self, status="Занимается"):
        self.kid.profile.hollihop_client_id = 777001
        self.kid.profile.hollihop_status = status
        self.kid.profile.save()

    def test_not_a_satmakon_student_gets_the_first_five(self):
        self.assertFalse(is_active_satmakon_student(self.kid))
        self.assertEqual(self.open_names(self.kid), ["DAY1", "DAY2", "DAY3", "DAY4", "DAY5"])

    def test_active_hollihop_status_opens_the_whole_library(self):
        self.make_active_by_status()
        self.assertTrue(is_active_satmakon_student(User.objects.get(pk=self.kid.pk)))
        self.assertEqual(len(self.open_names(self.kid)), 8)

    def test_inactive_hollihop_status_is_not_enough(self):
        self.make_active_by_status("Не занимается")
        self.assertEqual(len(self.open_names(self.kid)), 5)

    def test_approved_hollihop_group_opens_the_whole_library(self):
        classroom = Classroom.objects.create(teacher=self.teacher, name="SAT group", is_active=True, hollihop_managed=True)
        membership = ClassroomMembership.objects.create(classroom=classroom, user=self.kid, role="student",
                                                        status="approved", approved_at=timezone.now())
        self.assertEqual(len(self.open_names(self.kid)), 8)
        membership.status = "removed"
        membership.save()
        self.assertEqual(len(self.open_names(self.kid)), 5)

    def test_a_finished_status_wins_over_a_group_that_was_not_cleaned_up(self):
        classroom = Classroom.objects.create(teacher=self.teacher, name="Old group", is_active=True, hollihop_managed=True)
        ClassroomMembership.objects.create(classroom=classroom, user=self.kid, role="student", status="approved",
                                           approved_at=timezone.now())
        self.make_active_by_status("Закончил обучение")
        self.assertEqual(len(self.open_names(self.kid)), 5)
        self.make_active_by_status("Занимается")
        self.assertEqual(len(self.open_names(self.kid)), 8)

    def test_a_teacher_grant_still_opens_a_test_beyond_the_free_five(self):
        classroom = Classroom.objects.create(teacher=self.teacher, name="Manual class", is_active=True)
        membership = ClassroomMembership.objects.create(classroom=classroom, user=self.kid, role="student",
                                                        status="approved", approved_at=timezone.now())
        StudentSectionAccess.objects.update_or_create(membership=membership, section="practice_tests",
                                                      defaults={"has_access": True})
        StudentPracticeTestAccess.objects.create(membership=membership, test=self.tests[7], has_access=True)
        self.assertEqual(self.open_names(self.kid), ["DAY1", "DAY2", "DAY3", "DAY4", "DAY5", "DAY8"])

    @override_settings(MAKONBOOK_FREE_PRACTICE_TESTS=2)
    def test_the_free_tier_size_is_a_setting(self):
        self.assertEqual(self.open_names(self.kid), ["DAY1", "DAY2"])

    def test_library_page_shows_locked_tests_and_opening_one_explains_why(self):
        self.client.force_login(self.kid)
        page = self.client.get(reverse("practice_tests_root"))
        self.assertContains(page, "is-membership-locked", count=3)
        self.assertContains(page, "available only to current SATMakon students")
        response = self.client.get(reverse("practice_test_start_root", args=["DAY7"]), follow=True)
        self.assertRedirects(response, reverse("practice_tests_root"))
        self.assertContains(response, "DAY7 is available only to current SATMakon students")
        self.assertEqual(self.client.get(reverse("practice_test_start_root", args=["DAY1"])).status_code, 200)

    def test_current_students_see_no_locks(self):
        self.make_active_by_status()
        self.client.force_login(self.kid)
        page = self.client.get(reverse("practice_tests_root"))
        self.assertNotContains(page, "is-membership-locked")
        self.assertEqual(self.client.get(reverse("practice_test_start_root", args=["DAY7"])).status_code, 200)


class JoinCodesOffTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("v77_t", password="x")
        self.teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.classroom = Classroom.objects.create(teacher=self.teacher, name="Manual", is_active=True)
        self.code = ClassroomJoinCode.objects.create(classroom=self.classroom, code="123456", is_active=True,
                                                     expires_at=timezone.now() + timezone.timedelta(hours=2))
        self.kid = User.objects.create_user("v77_k", password="x")

    def test_students_cannot_request_a_classroom_by_code(self):
        self.client.force_login(self.kid)
        response = self.client.post(reverse("student_join_classroom_request_root"), {"code": "123456"},
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 403)
        self.client.post(reverse("events"), {"code": "123456"})
        self.client.post(reverse("enter_secret_code"), {"code": "123456"})
        self.assertFalse(ClassroomMembership.objects.filter(user=self.kid).exists())
        page = self.client.get(reverse("student_classrooms_root"))
        self.assertNotContains(page, "data-classroom-join-layer")
        self.assertNotContains(page, ">Join classroom</button>", html=False)

    def test_teachers_cannot_issue_codes(self):
        self.client.force_login(self.teacher)
        self.code.delete()
        self.client.post(reverse("teacher_generate_classroom_join_code_root", args=[self.classroom.pk]))
        self.assertFalse(ClassroomJoinCode.objects.filter(classroom=self.classroom).exists())
        self.assertNotContains(self.client.get(reverse("teacher_classroom_root", args=[self.classroom.pk])),
                               "Generate join code")

    @override_settings(MAKONBOOK_CLASSROOM_JOIN_CODES=True)
    def test_codes_can_be_switched_back_on(self):
        self.client.force_login(self.kid)
        response = self.client.post(reverse("student_join_classroom_request_root"), {"code": "123456"},
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ClassroomMembership.objects.filter(user=self.kid, status="pending").exists())

"""V73 A-to-Z audit: privilege escalation holes, CSRF-able writes and 500s found by the crawl."""
from datetime import date

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.ratings.models import AssessmentObligation, AssessmentSchedule
from apps.sat.models import Classroom, ClassroomMembership, Mock, Punishment, Test, TestImportJob


class AdminPanelHolesTests(TestCase):
    """Three admin views were only @login_required: any student could use them."""

    def setUp(self):
        self.student = User.objects.create_user("sec_student", password="x")
        self.admin = User.objects.create_user("sec_admin", password="x")
        self.admin_group = Group.objects.get_or_create(name="Admin")[0]
        self.admin.groups.add(self.admin_group)

    def test_student_cannot_create_an_admin_account(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("admin_user_create"), {
            "username": "evil", "password": "x", "group": self.admin_group.pk,
        })
        self.assertNotEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="evil").exists())

    def test_admin_can_create_users_and_a_bad_group_does_not_crash(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("admin_user_create"), {"username": "newbie1", "password": "x", "group": self.admin_group.pk})
        self.assertTrue(User.objects.get(username="newbie1").groups.filter(name="Admin").exists())
        response = self.client.post(reverse("admin_user_create"), {"username": "newbie2", "password": "x", "group": "999999"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.get(username="newbie2").groups.exists())

    def test_student_cannot_change_which_tests_a_group_gets(self):
        group = Group.objects.create(name="Paid SAT")
        test = Test.objects.create(name="PREMIUM-1")
        self.client.force_login(self.student)
        self.client.post(reverse("edit_group_tests", args=[group.pk]), {"tests": [test.pk]})
        self.assertFalse(group.tests.exists())

    def test_student_cannot_delete_a_mock(self):
        mock = Mock.objects.create(name="Mock Nov", mode="direct", user_count=10)
        self.client.force_login(self.student)
        self.client.post(reverse("admin_mock_delete", args=[mock.pk]), {"confirmation_name": "Mock Nov"})
        self.assertTrue(Mock.objects.filter(pk=mock.pk).exists())


class CrashFixesTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("sec_teacher", password="x")
        self.teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.student = User.objects.create_user("sec_kid", password="x")
        self.admin = User.objects.create_user("sec_admin2", password="x")
        self.admin.groups.add(Group.objects.get_or_create(name="Admin")[0])

    def test_unknown_test_results_are_404_not_500(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("practice_test_results_root", args=["NO SUCH TEST"])).status_code, 404)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("results_by_user", args=["NO SUCH TEST", "nobody"])).status_code, 404)

    def protected_classroom(self):
        classroom = Classroom.objects.create(teacher=self.teacher, name="Rated class", is_active=True)
        ClassroomMembership.objects.create(classroom=classroom, user=self.student, role="student", status="approved",
                                           approved_at=timezone.now())
        schedule = AssessmentSchedule.objects.create(classroom=classroom, teacher=self.teacher, weekdays=[1])
        AssessmentObligation.objects.create(schedule=schedule, student=self.student, lesson_date=date.today())
        return classroom

    def test_deleting_a_classroom_with_assessment_history_archives_it(self):
        classroom = self.protected_classroom()
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("delete_classroom", args=[classroom.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        classroom.refresh_from_db()
        self.assertFalse(classroom.is_active)
        self.assertContains(response, "archived instead of deleted")

    def test_deleting_a_user_with_assessment_records_deactivates_them(self):
        self.protected_classroom()
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin_user_delete", args=[self.student.pk]))
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)

    def test_unknown_import_job_audit_is_404(self):
        manager = User.objects.create_user("sec_manager", password="x")
        manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.client.force_login(manager)
        self.assertFalse(TestImportJob.objects.filter(pk=987654).exists())
        response = self.client.post(reverse("manager_test_import_audit_batch_root", args=[987654]))
        self.assertEqual(response.status_code, 404)

    def test_punishment_cannot_be_triggered_by_a_cross_site_get(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get("/sat/punishment/DAY1").status_code, 405)
        self.assertFalse(Punishment.objects.exists())

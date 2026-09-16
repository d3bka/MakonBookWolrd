from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    Classroom,
    ClassroomHomeworkAssignment,
    ClassroomJoinCode,
    ClassroomMembership,
    SupportTeacherProfile,
    SupportTeacherProfileSection,
    Test,
)


class StaffWorkspaceV529Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        teacher_group = Group.objects.get_or_create(name="Teacher")[0]
        manager_group = Group.objects.get_or_create(name="Manager")[0]
        cls.teacher = User.objects.create_user("teacher_v529", password="pass12345", first_name="V529")
        cls.teacher.groups.add(teacher_group)
        cls.manager = User.objects.create_user("manager_v529", password="pass12345")
        cls.manager.groups.add(manager_group)
        cls.sat = Classroom.objects.create(teacher=cls.teacher, name="SAT V529", classroom_type="sat")
        cls.ap = Classroom.objects.create(teacher=cls.teacher, name="AP V529", classroom_type="ap")
        cls.student = User.objects.create_user("student_v529", password="pass12345")
        ClassroomMembership.objects.create(classroom=cls.sat, user=cls.student, role="student", status="approved")
        cls.test = Test.objects.create(name="DAY V529", is_available=True)

    def test_homework_modal_uses_model_assignment_values_and_can_create_sat_homework(self):
        self.client.force_login(self.teacher)
        page = self.client.get(reverse("teacher_homework_root"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'value="sat_test"')
        self.assertContains(page, 'value="vocabulary_unit"')
        self.assertContains(page, "staff-workspace-v529.css")
        response = self.client.post(reverse("teacher_homework_root"), {
            "classroom": self.sat.pk,
            "assignment_type": "sat_test",
            "title": "V529 Homework",
            "test": self.test.pk,
        })
        self.assertRedirects(response, reverse("teacher_homework_root"), fetch_redirect_response=False)
        self.assertTrue(ClassroomHomeworkAssignment.objects.filter(title="V529 Homework", test=self.test).exists())

    def test_access_hub_hides_ap_events_for_sat_and_shows_them_for_ap(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("teacher_access_root"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("SAT V529", html)
        self.assertIn("AP V529", html)
        self.assertEqual(html.count(">AP events<"), 1)
        self.assertIn("data-v50210-access-open", html)

    def test_classroom_dashboard_restores_join_code_expiry_copy(self):
        ClassroomJoinCode.objects.create(
            classroom=self.sat,
            code="V529AA",
            expires_at=timezone.now() + timedelta(hours=12),
            is_active=True,
        )
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("teacher_classroom_root", args=[self.sat.pk]))
        self.assertContains(response, "This code expires")
        self.assertContains(response, "Regenerating it invalidates the current code immediately")

    def test_teacher_can_add_linkedin_style_custom_profile_section(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("mentor_profile_edit_root"), {
            "profile_action": "add_custom_section",
            "section_title": "Projects",
            "section_body": "Built an SAT analytics dashboard.",
            "section_url": "https://example.com/project",
        })
        self.assertRedirects(response, reverse("mentor_profile_edit_root"), fetch_redirect_response=False)
        profile = SupportTeacherProfile.objects.get(user=self.teacher)
        self.assertTrue(SupportTeacherProfileSection.objects.filter(profile=profile, title="Projects").exists())

    def test_published_tests_page_supports_search_and_view_toggle(self):
        Test.objects.create(name="UNRELATED V529", is_available=False)
        self.client.force_login(self.manager)
        response = self.client.get(reverse("manager_managed_test_list_root"), {"q": "DAY V529", "state": "open"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DAY V529")
        self.assertNotContains(response, "UNRELATED V529")
        self.assertContains(response, 'data-sf29-view-toggle="published-tests"')

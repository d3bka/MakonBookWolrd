"""V97: a Teacher+Manager+Admin opening Hollihop stays in the Manager (or Admin) workspace."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse


class HollihopWorkspaceModeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("v97_multi", password="x", is_staff=True)
        for name in ("Teacher", "Manager"):
            self.user.groups.add(Group.objects.get_or_create(name=name)[0])
        self.client.force_login(self.user)

    def test_hollihop_opens_in_the_manager_workspace(self):
        page = self.client.get(reverse("hollihop_dashboard"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'data-staff-mode="manager"')
        self.assertContains(page, "Manager workspace")
        self.assertNotContains(page, "Teacher workspace")

    def test_hollihop_from_the_admin_sidebar_stays_in_admin(self):
        page = self.client.get(reverse("hollihop_dashboard") + "?workspace=admin")
        self.assertContains(page, 'data-staff-mode="admin"')
        self.assertContains(page, reverse("hollihop_dashboard") + "?workspace=admin")

    def test_seasonal_theme_from_the_admin_sidebar_stays_in_admin(self):
        page = self.client.get(reverse("manager_seasonal_theme") + "?workspace=admin")
        self.assertContains(page, 'data-staff-mode="admin"')

    def test_a_teacher_only_account_cannot_ask_for_the_admin_workspace(self):
        teacher = User.objects.create_user("v97_teacher", password="x")
        teacher.groups.add(Group.objects.get(name="Teacher"))
        self.client.force_login(teacher)
        page = self.client.get(reverse("settings_page") + "?workspace=admin")
        self.assertNotContains(page, 'data-staff-mode="admin"')

    def test_teacher_pages_still_use_the_teacher_workspace(self):
        page = self.client.get(reverse("teacher_dashboard_root"))
        self.assertContains(page, 'data-staff-mode="teacher"')

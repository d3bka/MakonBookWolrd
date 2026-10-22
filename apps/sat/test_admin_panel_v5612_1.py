from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


class AdminPanelV56121Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="admin_panel_56121",
            email="admin-panel-56121@example.com",
            password="StrongPass-56121",
        )
        self.client.force_login(self.user)

    def test_custom_admin_panel_uses_unified_staff_workspace(self):
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-staff-workspace')
        self.assertContains(response, 'data-staff-mode="admin"')
        self.assertContains(response, 'Admin workspace')
        self.assertContains(response, 'admin-workspace-v5612-2.css')
        self.assertContains(response, 'Placement leads')
        self.assertContains(response, 'Django admin')
        self.assertContains(response, 'Recent level checks')
        self.assertNotContains(response, 'data-admin-shell')
        self.assertNotContains(response, 'admin-panel-v5612-1.css')
        self.assertNotContains(response, 'class="breadcrumbs"')

    def test_teacher_manager_admin_user_can_switch_all_three_workspaces(self):
        User = get_user_model()
        multi = User.objects.create_user(
            username="three_role_56122",
            password="StrongPass-56122",
            first_name="Three",
            last_name="Role",
        )
        for name in ("Teacher", "Manager", "Admin"):
            group, _ = Group.objects.get_or_create(name=name)
            multi.groups.add(group)
        self.client.force_login(multi)

        admin_response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, 'data-staff-mode="admin"')
        self.assertContains(admin_response, reverse("teacher_dashboard_root"))
        self.assertContains(admin_response, reverse("manager_dashboard_root"))
        self.assertContains(admin_response, reverse("admin_dashboard"))
        self.assertContains(admin_response, '>Teacher</span>', html=False)
        self.assertContains(admin_response, '>Manager</span>', html=False)
        self.assertContains(admin_response, '>Admin</span>', html=False)

        manager_response = self.client.get(reverse("manager_dashboard_root"))
        self.assertEqual(manager_response.status_code, 200)
        self.assertContains(manager_response, 'data-staff-mode="manager"')
        self.assertContains(manager_response, reverse("admin_dashboard"))

        teacher_response = self.client.get(reverse("teacher_dashboard_root"))
        self.assertEqual(teacher_response.status_code, 200)
        self.assertContains(teacher_response, 'data-staff-mode="teacher"')
        self.assertContains(teacher_response, reverse("admin_dashboard"))

    def test_admin_account_pages_preserve_admin_workspace_when_requested(self):
        response = self.client.get(reverse("settings_page") + "?workspace=admin")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-staff-mode="admin"')
        self.assertContains(response, 'Admin workspace')

    def test_mock_exams_use_landing_header(self):
        template = (Path(settings.BASE_DIR) / "templates/sat/guest/event_list.html").read_text(encoding="utf-8")
        self.assertIn("landing/_public_header.html", template)
        self.assertIn("makon-landing-v5597.css", template)
        self.assertIn("mock-public-header-v5612-1.css", template)
        self.assertNotIn('class="mkp-nav" data-public-nav', template)

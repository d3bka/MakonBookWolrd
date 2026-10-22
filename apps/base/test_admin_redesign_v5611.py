from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.sat.models import PublicPlacementLead


class MakonAdminV5611Tests(TestCase):
    """Regression contract after V5612.1: native Django design, MakonBook data tools."""

    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username="admin_v5611",
            email="admin-v5611@example.com",
            password="StrongPass-5611",
        )
        self.client.force_login(self.admin_user)

    def test_admin_index_uses_native_django_layout(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MakonBook administration")
        self.assertContains(response, "Site administration")
        self.assertNotContains(response, "makon-admin-v5611.css")
        self.assertNotContains(response, "Admin control center")

    def test_admin_branding_keeps_native_admin_site(self):
        self.assertEqual(admin.site.site_header, "MakonBook administration")
        self.assertEqual(admin.site.site_title, "MakonBook admin")
        self.assertEqual(admin.site.index_title, "Site administration")
        self.assertIn(PublicPlacementLead, admin.site._registry)

    def test_public_placement_admin_has_progress_and_result_columns(self):
        model_admin = admin.site._registry[PublicPlacementLead]
        self.assertIn("attempt_status", model_admin.list_display)
        self.assertIn("progress_display", model_admin.list_display)
        self.assertIn("result_display", model_admin.list_display)
        self.assertEqual(model_admin.date_hierarchy, "created_at")

    def test_project_does_not_override_native_admin_templates(self):
        base = Path(settings.BASE_DIR)
        self.assertFalse((base / "templates/admin/index.html").exists())
        self.assertFalse((base / "templates/admin/base_site.html").exists())
        self.assertFalse((base / "static/assets/css/makon-admin-v5611.css").exists())

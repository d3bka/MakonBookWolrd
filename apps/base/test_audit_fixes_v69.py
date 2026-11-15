"""V69 audit regressions: public data exposure and per-render DB writes."""
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.base.models import GeneralIssueReport
from apps.sat.models import MakonNotification, Test

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class IssueReportAttachmentTests(TestCase):
    def _post(self, upload):
        return self.client.post(reverse("submit_general_issue_report"), {
            "message": "The vocabulary page does not load on my phone.",
            "attachment": upload,
        })

    def test_real_png_is_accepted_and_renamed_unguessably(self):
        response = self._post(SimpleUploadedFile("IMG_1234.png", PNG, content_type="image/png"))
        self.assertEqual(response.status_code, 200)
        name = GeneralIssueReport.objects.get().attachment.name
        self.assertTrue(name.endswith(".png"))
        self.assertNotIn("IMG_1234", name)

    def test_html_disguised_as_png_is_rejected(self):
        response = self._post(SimpleUploadedFile("phish.html", b"<html><script>x</script>", content_type="image/png"))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(GeneralIssueReport.objects.exists())

    def test_png_bytes_with_html_extension_are_rejected(self):
        response = self._post(SimpleUploadedFile("phish.html", PNG, content_type="image/png"))
        self.assertEqual(response.status_code, 400)

    def test_svg_is_rejected(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>x</script></svg>'
        response = self._post(SimpleUploadedFile("a.png", svg, content_type="image/png"))
        self.assertEqual(response.status_code, 400)


class RankingsRequireLoginTests(TestCase):
    def test_anonymous_cannot_read_rankings(self):
        Test.objects.create(name="DAY 60")
        for url in (reverse("practice_test_rankings_root", args=["DAY 60"]), reverse("rankings", args=["DAY 60"])):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn("login", response.url)

    def test_only_admins_and_managers_read_rankings(self):
        # V74: names and SAT scores are private; a signed-in student must not see them.
        from django.contrib.auth.models import Group
        Test.objects.create(name="DAY 60")
        self.client.force_login(User.objects.create_user("ranker", password="x"))
        self.assertEqual(self.client.get(reverse("rankings", args=["DAY 60"])).status_code, 403)
        admin = User.objects.create_user("ranker-admin", password="x")
        admin.groups.add(Group.objects.get_or_create(name="Admin")[0])
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("rankings", args=["DAY 60"])).status_code, 200)


class NotificationCleanupOncePerSessionTests(TestCase):
    def test_legacy_notice_cleanup_runs_once_per_session(self):
        user = User.objects.create_user("cleanup-student", password="x")
        self.client.force_login(user)
        MakonNotification.objects.create(user=user, type=MakonNotification.TYPE_HOMEWORK, title="Homework removed: old")
        self.client.get(reverse("settings_page"))
        self.assertFalse(MakonNotification.objects.filter(title__startswith="Homework removed:").exists())
        # A notice appearing later in the same session is left alone: no DELETE per page.
        MakonNotification.objects.create(user=user, type=MakonNotification.TYPE_HOMEWORK, title="Homework removed: new")
        self.client.get(reverse("settings_page"))
        self.assertTrue(MakonNotification.objects.filter(title="Homework removed: new").exists())

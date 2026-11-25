"""V108: Settings → Platform version shows the current release from one setting."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


class PlatformVersionTests(TestCase):
    @override_settings(MAKONBOOK_VERSION="V999")
    def test_settings_page_shows_the_release(self):
        self.client.force_login(User.objects.create_user("ver_student", password="x"))
        page = self.client.get(reverse("settings_page"))
        self.assertContains(page, "MakonBook V999")
        self.assertContains(page, 'data-version="V999"')
        self.assertNotContains(page, "V50.2.8")

"""V78: every role has its own practice-test library (/<role>/practice-tests/) and Back goes there."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from apps.sat.models import SupportTeacherProfile, Test
from apps.sat.student_access import practice_library_url

LIBRARY = {
    "student": "/student/practice-tests/",
    "teacher": "/teacher/practice-tests/",
    "manager": "/manager/practice-tests/",
    "support": "/support-teacher/practice-tests/",
    "admin": "/sat/admin-panel/practice-tests/",
}


def make_user(role):
    user = User.objects.create_user(f"v78_{role}", password="x")
    group = {"teacher": "Teacher", "manager": "Manager", "support": "Support Teacher", "admin": "Admin"}.get(role)
    if group:
        user.groups.add(Group.objects.get_or_create(name=group)[0])
    if role == "support":
        SupportTeacherProfile.objects.create(user=user, display_name="Mentor", is_active=True)
    return user


class PracticeLibraryUrlTests(TestCase):
    def setUp(self):
        self.test = Test.objects.create(name="DAY1", is_available=True)
        self.users = {role: make_user(role) for role in LIBRARY}

    def test_each_role_has_its_own_library_address(self):
        for role, url in LIBRARY.items():
            self.assertEqual(practice_library_url(self.users[role]), url, role)

    def test_each_role_opens_its_library(self):
        for role, url in LIBRARY.items():
            self.client.force_login(self.users[role])
            self.assertEqual(self.client.get(url).status_code, 200, role)

    def test_the_old_tests_address_sends_each_role_to_its_library(self):
        for role, url in LIBRARY.items():
            self.client.force_login(self.users[role])
            self.assertRedirects(self.client.get("/tests/"), url, fetch_redirect_response=False, msg_prefix=role)

    def test_staff_opening_the_student_library_land_in_their_own(self):
        for role in ("teacher", "manager", "support", "admin"):
            self.client.force_login(self.users[role])
            response = self.client.get(LIBRARY["student"])
            self.assertRedirects(response, LIBRARY[role], fetch_redirect_response=False, msg_prefix=role)

    def test_back_on_the_test_preview_returns_to_the_role_library(self):
        start = reverse("practice_test_start_root", args=[self.test.name])
        for role, url in LIBRARY.items():
            self.client.force_login(self.users[role])
            page = self.client.get(start)
            self.assertEqual(page.status_code, 200, role)
            self.assertContains(page, f'href="{url}"', msg_prefix=role)
            self.assertNotContains(page, 'href="/tests/"', msg_prefix=role)

    def test_other_roles_cannot_open_a_staff_library(self):
        self.client.force_login(self.users["student"])
        for role in ("teacher", "manager", "support", "admin"):
            self.assertNotEqual(self.client.get(LIBRARY[role]).status_code, 200, role)

    def test_anonymous_visitors_are_asked_to_sign_in(self):
        self.client.logout()
        response = self.client.get("/tests/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

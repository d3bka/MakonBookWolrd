"""V74 device/design audit regressions (rankings privacy, styled allauth, World toast, runner loading)."""
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.sat.models import Test, TestReview


def member(name, *groups):
    user = User.objects.create_user(name, password="x", first_name=name.title())
    for group in groups:
        user.groups.add(Group.objects.get_or_create(name=group)[0])
    return user


class RankingsPrivacyTests(TestCase):
    def setUp(self):
        self.test = Test.objects.create(name="V74-DAY1", is_available=True)
        self.kid = member("v74_kid")
        TestReview.objects.create(user=self.kid, test=self.test, key="v74-review", score=1400)
        self.url = reverse("practice_test_rankings_root", args=[self.test.name])

    def test_students_and_teachers_cannot_see_other_students_scores(self):
        for who in (self.kid, member("v74_teacher", "Teacher")):
            self.client.force_login(who)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 403, who.username)
            self.assertNotIn(b"1400", response.content)

    def test_admins_and_managers_see_the_ranking(self):
        for who in (member("v74_admin", "Admin"), member("v74_manager", "Manager")):
            self.client.force_login(who)
            response = self.client.get(self.url)
            self.assertContains(response, "1400")
            self.assertNotContains(response, "xzx")  # stray text that used to render on the page

    def test_empty_and_unknown_tests(self):
        self.client.force_login(member("v74_admin2", "Admin"))
        empty = Test.objects.create(name="V74-EMPTY", is_available=True)
        self.assertContains(self.client.get(reverse("practice_test_rankings_root", args=[empty.name])), "No finished attempts")
        self.assertEqual(self.client.get(reverse("practice_test_rankings_root", args=["NOPE"])).status_code, 404)


class StyledPagesTests(TestCase):
    def test_allauth_pages_use_the_makonbook_shell(self):
        response = self.client.get("/accounts/login/")
        self.assertContains(response, "MakonBook account")
        self.assertContains(response, "makon-public-v5597.css")
        self.assertNotContains(response, "Menu:")

    def test_admin_group_tests_page_uses_the_admin_layout(self):
        self.client.force_login(member("v74_admin3", "Admin"))
        group = Group.objects.create(name="V74 cohort")
        Test.objects.create(name="V74-T1", is_available=True)
        response = self.client.get(reverse("edit_group_tests", args=[group.pk]))
        self.assertContains(response, "Assigned tests")
        self.assertContains(response, 'for="id_tests_0"')

    def test_favicon(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 301)
        self.assertIn("original-icon-nobg.png", response["Location"])


@override_settings(MAKONBOOK_WORLD_ENABLED=True)
class WorldChallengeToastTests(TestCase):
    """The duel toast polls a student-only endpoint; staff on student pages got a 403 every few seconds."""

    def test_toast_only_for_students(self):
        self.client.force_login(member("v74_student"))
        self.assertContains(self.client.get(reverse("vocabulary_root")), "data-challenge-toast")
        self.client.force_login(member("v74_teacher2", "Teacher"))
        self.assertNotContains(self.client.get(reverse("vocabulary_root")), "data-challenge-toast")


class FrontEndLoadingTests(TestCase):
    """Static checks: the exam runner must not wait for a CDN, editors must not need a cloud key."""

    def read(self, rel):
        return (Path(settings.BASE_DIR) / rel).read_text(encoding="utf-8")

    def test_exam_runners_do_not_block_on_katex(self):
        for name in ("templates/test/shared/attempt_eng.html", "templates/test/shared/attempt_math.html"):
            html = self.read(name)
            self.assertNotIn('<script src="https://cdn.jsdelivr.net/npm/katex', html, name)
            self.assertNotIn('<script defer src="https://cdn.jsdelivr.net/npm/katex', html, name)
            self.assertIn("makon:katex-ready", html, name)
        for name in ("static/assets/js/test-eng.js", "static/assets/js/test-math.js"):
            self.assertIn("makon:katex-ready", self.read(name), name)

    def test_vocabulary_question_editor_is_self_hosted(self):
        html = self.read("templates/sat/create_vocabulary_question.html")
        self.assertNotIn("no-api-key", html)
        self.assertIn("tinymce@6.8.5", html)

    def test_cdn_scripts_are_pinned(self):
        self.assertIn("chart.js@4.4.6", self.read("templates/test/results.html"))
        self.assertNotIn("hls.js@latest", self.read("templates/test/review/video.html"))

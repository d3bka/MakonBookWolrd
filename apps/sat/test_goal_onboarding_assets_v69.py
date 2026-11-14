"""V69: the goal onboarding modal must always ship with its stylesheet.

Home (/dashboard/) included the V65 onboarding markup without
makon-onboarding-v65.css, so first login and "Edit goal" rendered the modal
unstyled (stacked columns, a full-width logo). /goals/ redirects students to
Home, so it was broken there too.
"""
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

TEMPLATES = Path(settings.BASE_DIR) / "templates"
ONBOARDING_CSS = "makon-onboarding-v65.css"


class GoalOnboardingAssetTests(SimpleTestCase):
    def test_every_template_with_the_goal_modal_loads_its_stylesheet(self):
        pages = [
            path for path in TEMPLATES.rglob("*.html")
            if "_student_goal_modal.html" in path.read_text(encoding="utf-8")
        ]
        self.assertTrue(pages)
        for path in pages:
            with self.subTest(template=str(path.relative_to(TEMPLATES))):
                self.assertIn(ONBOARDING_CSS, path.read_text(encoding="utf-8"))

    def test_shell_overrides_the_global_section_padding(self):
        css = (Path(settings.BASE_DIR) / "static/assets/css" / ONBOARDING_CSS).read_text(encoding="utf-8")
        shell_rule = css.split(".mb65-onboard .mb65-shell.sg-goal-modal-panel{", 1)[1].split("}", 1)[0]
        self.assertIn("padding:0!important", shell_rule)


class GoalOnboardingHomeTests(TestCase):
    def test_home_and_goal_editor_render_onboarding_stylesheet(self):
        self.client.force_login(User.objects.create_user("onboard-student", password="x", first_name="A", last_name="B"))
        response = self.client.get(reverse("student_dashboard_root") + "?goal=1")
        self.assertContains(response, "data-mb65-onboard")
        self.assertContains(response, ONBOARDING_CSS)
        self.assertContains(response, 'data-auto-open="1"')


class GoalSingleBlockEditorTests(TestCase):
    def setUp(self):
        from datetime import date
        from apps.sat.models import DreamUniversity, StudentGoalProfile
        from apps.sat.student_goal_forms import OFFICIAL_SAT_DATES

        self.user = User.objects.create_user("edit-student", password="x", first_name="A", last_name="B")
        university = DreamUniversity.objects.create(name="Test University", country="United States", qs_rank=5)
        exam = next(d for d in OFFICIAL_SAT_DATES if d > date.today())
        StudentGoalProfile.objects.create(user=self.user, dream_university=university,
                                          target_sat_score=1500, exam_date=exam)
        self.client.force_login(self.user)

    def test_each_dashboard_edit_button_targets_its_own_block(self):
        response = self.client.get(reverse("student_dashboard_root"))
        for block in ("target", "uni", "date"):
            with self.subTest(block=block):
                self.assertContains(response, f'data-goal-edit="{block}"')
        self.assertContains(response, "Change date")  # editable even once a date is set

    def test_modal_knows_the_plan_is_configured_and_has_editor_chrome(self):
        response = self.client.get(reverse("student_dashboard_root"))
        self.assertContains(response, 'data-goal-configured="1"')
        self.assertContains(response, "data-mb69-edit-head")
        self.assertContains(response, "data-mb69-save")

    def test_unconfigured_plan_is_flagged_for_the_wizard(self):
        other = User.objects.create_user("new-student", password="x", first_name="C", last_name="D")
        self.client.force_login(other)
        response = self.client.get(reverse("student_dashboard_root"))
        self.assertContains(response, 'data-goal-configured="0"')

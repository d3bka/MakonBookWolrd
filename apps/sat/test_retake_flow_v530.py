
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.sat.models import English_Question, Test, TestReview, TestStage


User = get_user_model()


class RetakeFlowV530Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="retake_v530",
            password="pass12345",
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.test = Test.objects.create(name="RETAKE V530", is_available=True)
        # The retake overview only exposes Start when the test has at least one real module.
        English_Question.objects.create(
            test=self.test, module="module_1", number=1, question="Retake test question", answer="A"
        )

    def _completed_stage(self, test=None):
        test = test or self.test
        stage = TestStage.objects.create(
            user=self.user,
            test=test,
            test_type="regular",
            stage=5,
        )
        TestReview.objects.create(
            user=self.user,
            test=test,
            test_type="regular",
            score=400,
            key=f"review-{test.name}",
            attempt_id=stage.attempt_id,
        )
        return stage

    def test_results_retake_opens_overview_without_creating_attempt(self):
        stage = self._completed_stage()
        old_attempt = stage.attempt_id
        old_count = stage.retake_count

        response = self.client.post(
            reverse("practice_test_restart_root", args=[self.test.name])
        )

        self.assertRedirects(
            response,
            reverse("practice_test_start_root", args=[self.test.name]) + "?retake=full",
            fetch_redirect_response=False,
        )
        stage.refresh_from_db()
        self.assertEqual(stage.attempt_id, old_attempt)
        self.assertEqual(stage.retake_count, old_count)

    def test_confirming_overview_creates_exactly_one_new_attempt(self):
        stage = self._completed_stage()
        old_attempt = stage.attempt_id

        response = self.client.post(
            reverse("practice_test_restart_root", args=[self.test.name]),
            {"confirm_start": "1"},
        )

        new_stage = (
            TestStage.objects
            .filter(user=self.user, test=self.test, test_type="regular")
            .exclude(pk=stage.pk)
            .get()
        )
        self.assertRedirects(
            response,
            reverse("practice_test_attempt_module_root", args=[self.test.name, new_stage.attempt_id]),
            fetch_redirect_response=False,
        )
        stage.refresh_from_db()
        self.assertEqual(stage.attempt_id, old_attempt)
        self.assertNotEqual(new_stage.attempt_id, old_attempt)
        self.assertEqual(new_stage.retake_count, 1)
        self.assertEqual(
            TestStage.objects.filter(user=self.user, test=self.test, test_type="regular").count(),
            2,
        )

    @patch("apps.sat.views.get_test_sequence", return_value=[("english", "m1")])
    def test_other_unfinished_test_blocks_new_attempt(self, _sequence):
        active_test = Test.objects.create(name="ACTIVE V530", is_available=True)
        active_stage = TestStage.objects.create(
            user=self.user,
            test=active_test,
            test_type="regular",
            stage=1,
        )
        target_stage = self._completed_stage()
        target_attempt = target_stage.attempt_id

        response = self.client.post(
            reverse("practice_test_restart_root", args=[self.test.name]),
            {"confirm_start": "1"},
        )

        self.assertRedirects(
            response,
            reverse("practice_test_attempt_module_root", args=[active_test.name, active_stage.attempt_id]),
            fetch_redirect_response=False,
        )
        target_stage.refresh_from_db()
        self.assertEqual(target_stage.attempt_id, target_attempt)
        active_stage.refresh_from_db()
        self.assertEqual(active_stage.retake_count, 0)

    @patch("apps.sat.views.get_test_sequence", return_value=[("english", "m1")])
    def test_retake_query_renders_start_overview_instead_of_results(self, _sequence):
        self._completed_stage()

        response = self.client.get(
            reverse("practice_test_start_root", args=[self.test.name]) + "?retake=full"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New full-test attempt")
        self.assertContains(response, 'name="confirm_start" value="1"')
        self.assertContains(response, "Exam Integrity")
        self.assertContains(response, "Standard")
        self.assertContains(response, 'name="integrity_mode" value="standard"')


    def test_configured_start_after_completed_review_opens_retake_overview(self):
        """Regression for the real DAY1 log: configured start must not 302 to old results."""
        stage = self._completed_stage()
        before_ids = list(
            TestStage.objects.filter(user=self.user, test=self.test).values_list("id", flat=True)
        )

        response = self.client.get(
            reverse("practice_test_start_root", args=[self.test.name])
            + "?configured=1&test_mode=full_test&integrity_mode=strict"
              "&integrity_max_violations=3&integrity_fullscreen_required=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Start new attempt")
        self.assertContains(response, 'name="confirm_start" value="1"')
        # v5552 regression: the configured retake cover must keep the visible
        # Exam Integrity card and must carry the selected strict config into the
        # confirmation POST.
        self.assertContains(response, "Exam Integrity")
        self.assertContains(response, "Strict")
        self.assertContains(response, 'name="integrity_mode" value="strict"')
        self.assertContains(response, 'name="integrity_max_violations" value="3"')
        self.assertContains(response, 'name="integrity_fullscreen_required" value="1"')
        self.assertContains(
            response,
            f'action="{reverse("practice_test_restart_root", args=[self.test.name])}"',
        )
        self.assertEqual(
            list(TestStage.objects.filter(user=self.user, test=self.test).values_list("id", flat=True)),
            before_ids,
        )
        stage.refresh_from_db()
        self.assertEqual(stage.stage, 5)

    def test_retake_confirmation_persists_strict_integrity_config(self):
        """The anti-cheat settings shown on the retake cover must reach the new stage."""
        old_stage = self._completed_stage()

        response = self.client.post(
            reverse("practice_test_restart_root", args=[self.test.name]),
            {
                "confirm_start": "1",
                "integrity_mode": "strict",
                "integrity_max_violations": "3",
                "integrity_fullscreen_required": "1",
            },
        )
        self.assertEqual(response.status_code, 302)

        new_stage = (
            TestStage.objects
            .filter(user=self.user, test=self.test, test_type="regular")
            .exclude(pk=old_stage.pk)
            .get()
        )
        self.assertEqual(new_stage.integrity_mode, "strict")
        self.assertEqual(new_stage.integrity_max_violations, 3)
        self.assertTrue(new_stage.integrity_fullscreen_required)
        self.assertTrue(new_stage.integrity_monitored_events)


    def test_bound_fresh_retake_survives_unexpected_start_fallback(self):
        """A redirect through /start/ must not reopen the old scored review."""
        old_stage = self._completed_stage()

        launch = self.client.post(
            reverse("practice_test_restart_root", args=[self.test.name]),
            {"confirm_start": "1"},
        )
        self.assertEqual(launch.status_code, 302)

        new_stage = (
            TestStage.objects
            .filter(user=self.user, test=self.test, test_type="regular")
            .exclude(pk=old_stage.pk)
            .get()
        )

        # Simulate the exact production symptom: an intermediate redirect lands
        # back on the ordinary start URL while the old scored review still exists.
        fallback = self.client.get(
            reverse("practice_test_start_root", args=[self.test.name])
        )
        self.assertRedirects(
            fallback,
            reverse("practice_test_attempt_module_root", args=[self.test.name, new_stage.attempt_id]),
            fetch_redirect_response=False,
        )

    @patch("apps.sat.views._stage_attempt_is_complete", return_value=True)
    def test_explicit_fresh_attempt_route_does_not_use_history_completion_heuristic(self, _complete):
        """Path-bound UUID wins even if a legacy completion heuristic misfires."""
        stage = TestStage.objects.create(
            user=self.user,
            test=self.test,
            test_type="regular",
            stage=1,
            mode="full_test",
        )

        response = self.client.get(
            reverse("practice_test_attempt_module_root", args=[self.test.name, stage.attempt_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "test/test_eng.html")
        self.assertEqual(response.context["attempt_id"], stage.attempt_id)


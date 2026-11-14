"""V69 safety regressions for Hollihop reconciliation and the webhook path."""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.integrations.hollihop import tasks
from apps.integrations.hollihop.client import HollihopAPIError, HollihopError
from apps.integrations.hollihop.reconcile import HollihopSmartReconciler, SmartSyncReport
from apps.integrations.hollihop.sync import SyncSummary, guard_classroom_deactivation
from apps.sat.models import Classroom


def _reconciler():
    reconciler = object.__new__(HollihopSmartReconciler)
    reconciler.engine = MagicMock()
    reconciler.engine.summary = SyncSummary()
    reconciler.engine.corporative_filter = None
    reconciler.engine._filter_edunits_by_learning_type.side_effect = lambda rows: rows
    reconciler.client = MagicMock()
    reconciler.report = SmartSyncReport()
    return reconciler


class ClassroomDeactivationGuardTests(SimpleTestCase):
    def test_all_classrooms_missing_is_refused(self):
        with self.assertRaises(HollihopError):
            guard_classroom_deactivation(deactivate_count=5, total_count=5)

    def test_large_ratio_is_refused_once_population_is_meaningful(self):
        with self.assertRaises(HollihopError):
            guard_classroom_deactivation(deactivate_count=6, total_count=12)

    def test_normal_churn_is_allowed(self):
        guard_classroom_deactivation(deactivate_count=2, total_count=12)
        guard_classroom_deactivation(deactivate_count=0, total_count=0)

    def test_single_classroom_can_still_close(self):
        # With one classroom an empty read and a real closure look identical;
        # blocking forever would be worse than the ratio guard's protection.
        guard_classroom_deactivation(deactivate_count=1, total_count=1)


@override_settings(HOLLIHOP_EDUNIT_CATALOG_SWEEP_MINUTES=60)
class CatalogSweepGuardTests(TestCase):
    def setUp(self):
        teacher = get_user_model().objects.create_user("sweep-teacher", password="x")
        for edunit_id in range(1, 13):
            Classroom.objects.create(
                name=f"Group {edunit_id}", teacher=teacher,
                hollihop_managed=True, hollihop_edunit_id=edunit_id, is_active=True,
            )

    def test_empty_catalog_does_not_deactivate_everything(self):
        reconciler = _reconciler()
        reconciler.client.get_ed_units.return_value = []
        with self.assertRaises(HollihopError):
            reconciler._edunit_catalog_sweep({}, timezone.now())
        self.assertEqual(Classroom.objects.filter(is_active=True).count(), 12)

    def test_small_drop_still_deactivates(self):
        reconciler = _reconciler()
        reconciler.client.get_ed_units.return_value = [{"Id": i} for i in range(1, 12)]
        reconciler._edunit_catalog_sweep({}, timezone.now())
        self.assertFalse(Classroom.objects.get(hollihop_edunit_id=12).is_active)
        self.assertEqual(Classroom.objects.filter(is_active=True).count(), 11)


class StudentDeltaIsolationTests(SimpleTestCase):
    def test_one_bad_row_does_not_stop_later_rows_or_advance_cursor(self):
        reconciler = _reconciler()
        reconciler.client.get_students.return_value = [{"ClientId": 1}, {"ClientId": 2}, {"ClientId": 3}]
        state = MagicMock(initial_sync_completed_at=None, last_successful_sync=None)
        cursor = {}
        with patch.object(
            HollihopSmartReconciler, "_sync_one_student_row",
            side_effect=[None, IntegrityError("dup"), None],
        ) as sync_row:
            reconciler._student_delta(state, cursor, timezone.now())
        self.assertEqual(sync_row.call_count, 3)
        self.assertEqual(reconciler.engine.summary.errors, 1)
        self.assertNotIn("students_delta_at", cursor)

    def test_api_failure_still_aborts_the_cycle(self):
        reconciler = _reconciler()
        reconciler.client.get_students.return_value = [{"ClientId": 1}, {"ClientId": 2}]
        state = MagicMock(initial_sync_completed_at=None, last_successful_sync=None)
        with patch.object(
            HollihopSmartReconciler, "_sync_one_student_row",
            side_effect=HollihopAPIError("down"),
        ) as sync_row:
            with self.assertRaises(HollihopAPIError):
                reconciler._student_delta(state, {}, timezone.now())
        self.assertEqual(sync_row.call_count, 1)

    def test_clean_run_advances_cursor(self):
        reconciler = _reconciler()
        reconciler.client.get_students.return_value = [{"ClientId": 1}]
        state = MagicMock(initial_sync_completed_at=None, last_successful_sync=None)
        cursor = {}
        with patch.object(HollihopSmartReconciler, "_sync_one_student_row", return_value=None):
            reconciler._student_delta(state, cursor, timezone.now())
        self.assertIn("students_delta_at", cursor)


class WebhookTaskRetryTests(SimpleTestCase):
    @patch.object(tasks, "_integration_enabled", return_value=True)
    @patch.object(tasks, "_initial_sync_ready", return_value=True)
    @patch.object(tasks.process_student_webhook, "apply_async")
    @patch.object(tasks, "_new_engine")
    def test_transient_api_error_is_retried_not_lost(self, new_engine, apply_async, *_):
        engine = new_engine.return_value
        engine.client.get_students.side_effect = HollihopAPIError("HTTP 503")
        result = tasks.process_student_webhook("Updated", 236, 0)
        self.assertEqual(result["status"], "retry_queued")
        apply_async.assert_called_once()
        self.assertEqual(apply_async.call_args.kwargs["args"], ["Updated", 236, 1])

    @patch.object(tasks, "_integration_enabled", return_value=True)
    @patch.object(tasks, "_initial_sync_ready", return_value=True)
    @patch.object(tasks.process_student_webhook, "apply_async")
    @patch.object(tasks, "_new_engine")
    def test_retries_are_bounded(self, new_engine, apply_async, *_):
        new_engine.return_value.client.get_students.side_effect = HollihopAPIError("HTTP 503")
        with self.assertRaises(HollihopAPIError):
            tasks.process_student_webhook("Updated", 236, 5)
        apply_async.assert_not_called()


@override_settings(
    SCHOOL_DATA_PROVIDER="hollihop",
    HOLLIHOP_ENABLED=True,
    HOLLIHOP_WEBHOOK_SECRET="secret123",
    HOLLIHOP_WEBHOOK_RATE_LIMIT=120,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "wh-v69"}},
)
class WebhookBrokerOutageTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch("apps.integrations.hollihop.views.process_student_webhook.apply")
    @patch("apps.integrations.hollihop.views.process_student_webhook.delay", side_effect=ConnectionError("broker down"))
    def test_broker_outage_returns_503_and_never_runs_sync_inline(self, _delay, apply):
        payload = {"key": "secret123", "TriggerType": "StatusSet", "ObjectType": "StudentClient", "ObjectId": "236"}
        with self.assertLogs("apps.integrations.hollihop.views", level="ERROR"):
            response = self.client.post(reverse("hollihop_webhook"), payload)
        self.assertEqual(response.status_code, 503)
        apply.assert_not_called()


class StudentDeltaQuarantineTests(SimpleTestCase):
    def _cycle(self, reconciler, cursor, outcome):
        reconciler.client.get_students.return_value = [{"ClientId": 77}, {"ClientId": 78}]
        state = MagicMock(initial_sync_completed_at=None, last_successful_sync=None)
        side_effect = [outcome, None]
        with patch.object(HollihopSmartReconciler, "_sync_one_student_row", side_effect=side_effect):
            reconciler._student_delta(state, cursor, timezone.now())

    @override_settings(HOLLIHOP_DELTA_ROW_MAX_FAILURES=3)
    def test_row_failing_three_cycles_is_quarantined_and_cursor_moves_on(self):
        reconciler, cursor = _reconciler(), {}
        self._cycle(reconciler, cursor, IntegrityError("dup"))
        self._cycle(reconciler, cursor, IntegrityError("dup"))
        self.assertNotIn("students_delta_at", cursor)
        reconciler.engine._conflict.assert_not_called()

        self._cycle(reconciler, cursor, IntegrityError("dup"))
        self.assertIn("students_delta_at", cursor)
        reconciler.engine._conflict.assert_called_once()
        self.assertEqual(reconciler.engine._conflict.call_args.kwargs["external_type"], "student_sync")
        self.assertEqual(reconciler.engine._conflict.call_args.kwargs["external_id"], "77")

        # A fourth failure neither blocks nor opens another conflict.
        del cursor["students_delta_at"]
        self._cycle(reconciler, cursor, IntegrityError("dup"))
        self.assertIn("students_delta_at", cursor)
        reconciler.engine._conflict.assert_called_once()

    def test_success_clears_the_failure_count(self):
        reconciler, cursor = _reconciler(), {}
        self._cycle(reconciler, cursor, IntegrityError("dup"))
        self.assertEqual(cursor["student_delta_failures"], {"77": 1})
        self._cycle(reconciler, cursor, None)
        self.assertNotIn("student_delta_failures", cursor)
        self.assertIn("students_delta_at", cursor)

    def test_soft_time_limit_and_lost_lease_are_never_swallowed(self):
        from celery.exceptions import SoftTimeLimitExceeded
        from apps.integrations.hollihop.sync import HollihopSyncAlreadyRunning

        for fatal in (SoftTimeLimitExceeded(), HollihopSyncAlreadyRunning("lease lost")):
            with self.subTest(fatal=type(fatal).__name__):
                reconciler = _reconciler()
                reconciler.client.get_students.return_value = [{"ClientId": 1}, {"ClientId": 2}]
                state = MagicMock(initial_sync_completed_at=None, last_successful_sync=None)
                with patch.object(HollihopSmartReconciler, "_sync_one_student_row", side_effect=fatal) as row:
                    with self.assertRaises(type(fatal)):
                        reconciler._student_delta(state, {}, timezone.now())
                self.assertEqual(row.call_count, 1)


class CeleryTimeLimitTests(SimpleTestCase):
    def test_global_limits_are_configured(self):
        from django.conf import settings
        self.assertGreater(settings.CELERY_TASK_SOFT_TIME_LIMIT, 0)
        self.assertGreater(settings.CELERY_TASK_TIME_LIMIT, settings.CELERY_TASK_SOFT_TIME_LIMIT)

    def test_long_jobs_have_explicit_bounded_limits(self):
        from apps.content_sync.tasks import sync_makonbook_api_content
        from apps.sat.tasks import convert_video_to_hls
        for task in (
            tasks.smart_reconcile_hollihop, tasks.reconcile_hollihop, tasks.manual_initial_hollihop_sync,
            tasks.process_student_webhook, sync_makonbook_api_content, convert_video_to_hls,
        ):
            with self.subTest(task=task.name):
                self.assertTrue(task.soft_time_limit)
                self.assertGreater(task.time_limit, task.soft_time_limit)

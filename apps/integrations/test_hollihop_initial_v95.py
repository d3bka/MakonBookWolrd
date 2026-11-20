"""V95: a few bad Hollihop rows no longer keep "Run initial sync" from finishing the setup."""
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.integrations.hollihop import tasks
from apps.integrations.hollihop.reconcile import initial_import_can_finish
from apps.integrations.hollihop.sync import HollihopSyncEngine, SyncSummary
from apps.integrations.models import HollihopSyncLog, HollihopSyncState
from apps.integrations.test_hollihop_e2e_v88 import PROD, edunit, rel, student, teacher
from apps.integrations.tests import FakeHollihopClient

LIVE = dict(PROD, HOLLIHOP_API_URL="https://school.t8s.ru/Api/V2", HOLLIHOP_AUTH_KEY="key")


@override_settings(**LIVE)
class InitialSyncFinishesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.manager = User.objects.create_user("v95_manager", password="x")
        self.manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.api = FakeHollihopClient()
        self.api.teachers = [teacher(501, "Aziz")]
        self.api.edunits = [edunit(9001, "SAT Math A", [501])]
        self.api.students = [student(1001, "Malika"), student(1002, "Bad Row")]
        self.api.relations = [rel(9001, 1001), rel(9001, 1002)]

    def engine_factory(self, **kwargs):
        engine = HollihopSyncEngine(client=self.api, send_credentials=False)
        engine.activity_kind = kwargs.get("kind", "sync")
        return engine

    def run_initial(self, fail_ids=()):
        original = HollihopSyncEngine._sync_student

        def flaky(engine, data):
            if data.get("ClientId") in fail_ids:
                raise ValueError("duplicate phone")
            return original(engine, data)

        with mock.patch.object(tasks, "_new_engine", self.engine_factory), \
                mock.patch.object(HollihopSyncEngine, "_sync_student", flaky):
            return tasks.manual_initial_hollihop_sync()

    def state(self):
        return HollihopSyncState.objects.get(provider="hollihop")

    def test_rule(self):
        self.assertTrue(initial_import_can_finish(SyncSummary()))
        self.assertTrue(initial_import_can_finish(SyncSummary(errors=3, students_found=120)))
        self.assertFalse(initial_import_can_finish(SyncSummary(errors=1)))

    def test_one_bad_row_still_finishes_the_setup(self):
        result = self.run_initial(fail_ids={1002})
        self.assertEqual(result["status"], "partial")
        state = self.state()
        self.assertTrue(state.initial_sync_completed)
        self.assertEqual(state.last_status, "partial")
        log = HollihopSyncLog.objects.get(event_type="initial_sync_completed")
        self.assertEqual(log.details["row_errors"], 1)
        self.assertTrue(User.objects.filter(profile__hollihop_client_id=1001).exists())

        self.client.force_login(self.manager)
        page = self.client.get(reverse("hollihop_dashboard"))
        self.assertContains(page, "Initial import finished")
        self.assertContains(page, "1 row(s) could not be imported")
        self.assertContains(page, "Check updates now")
        self.assertNotContains(page, ">Run initial sync<")

    def test_a_clean_import_finishes_without_a_warning(self):
        self.run_initial()
        self.assertTrue(self.state().initial_sync_completed)
        self.client.force_login(self.manager)
        page = self.client.get(reverse("hollihop_dashboard"))
        self.assertContains(page, "Initial import finished")
        self.assertNotContains(page, "could not be imported")

    def test_an_import_that_brought_nothing_does_not_finish(self):
        self.api.teachers, self.api.edunits, self.api.students, self.api.relations = [], [], [], []

        def failing_managers(engine):
            engine.summary.errors += 1  # e.g. the only rows Hollihop returned were broken

        with mock.patch.object(tasks, "_new_engine", self.engine_factory), \
                mock.patch.object(HollihopSyncEngine, "sync_managers", failing_managers):
            tasks.manual_initial_hollihop_sync()
        state = HollihopSyncState.objects.filter(provider="hollihop").first()
        self.assertFalse(state and state.initial_sync_completed)

    def test_an_aborted_import_does_not_finish_and_the_panel_says_so(self):
        with mock.patch.object(tasks, "_new_engine", self.engine_factory), \
                mock.patch.object(HollihopSyncEngine, "sync_students", side_effect=RuntimeError("Hollihop is down")):
            with self.assertRaises(RuntimeError):
                tasks.manual_initial_hollihop_sync()
        self.assertFalse(self.state().initial_sync_completed)
        self.client.force_login(self.manager)
        page = self.client.get(reverse("hollihop_dashboard"))
        self.assertContains(page, "The last import did not finish the setup")
        self.assertContains(page, ">Run initial sync<")

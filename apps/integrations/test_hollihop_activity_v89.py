"""V89: managers see when a Hollihop synchronization is queued or running, and which stage."""
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.integrations.hollihop import activity
from apps.integrations.hollihop.sync import HollihopSyncEngine
from apps.integrations.models import HollihopSyncState
from apps.integrations.test_hollihop_e2e_v88 import PROD, edunit, rel, student, teacher
from apps.integrations.tests import FakeHollihopClient

LIVE = dict(PROD, HOLLIHOP_API_URL="https://school.t8s.ru/Api/V2", HOLLIHOP_AUTH_KEY="key")


@override_settings(**LIVE)
class SyncActivityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.manager = User.objects.create_user("v89_manager", password="x")
        self.manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.client.force_login(self.manager)
        self.api = FakeHollihopClient()
        self.api.teachers = [teacher(501, "Aziz")]
        self.api.edunits = [edunit(9001, "SAT Math A", [501])]
        self.api.students = [student(1001, "Malika")]
        self.api.relations = [rel(9001, 1001)]

    def page(self):
        return self.client.get(reverse("hollihop_dashboard"))

    def test_idle_shows_nothing_running(self):
        self.assertEqual(activity.current()["status"], "idle")
        response = self.page()
        self.assertContains(response, 'class="holli-live is-idle"')
        self.assertNotContains(response, 'class="mb89-sync-dot"')

    def test_a_running_sync_shows_kind_stage_counts_and_the_sidebar_dot(self):
        engine = HollihopSyncEngine(client=self.api)
        engine.activity_kind = "full"
        engine.acquire_lock()
        engine.stage("students")
        engine.summary.students_found = 42
        engine.heartbeat_lock(force=True)

        data = self.client.get(reverse("hollihop_sync_activity")).json()
        self.assertEqual(data["status"], "running")
        self.assertEqual((data["kind_label"], data["stage_label"]), ("Full reconciliation", "Students"))
        self.assertIn({"label": "students", "value": 42}, data["counts"])
        response = self.page()
        self.assertContains(response, "Full reconciliation in progress")
        self.assertContains(response, 'class="holli-live-stage">Students<')
        self.assertContains(response, 'class="mb89-sync-dot"')
        self.assertContains(response, "mb89-spin")

        engine.release_lock(success=True)
        self.assertEqual(activity.current()["status"], "idle")
        self.assertNotContains(self.page(), 'class="mb89-sync-dot"')

    def test_pressing_a_button_shows_queued_until_a_worker_starts(self):
        HollihopSyncState.objects.create(provider="hollihop", initial_sync_completed=True)
        with mock.patch("apps.integrations.hollihop.views.manual_smart_hollihop_sync.delay"):
            self.client.post(reverse("hollihop_smart_sync"))
        data = self.client.get(reverse("hollihop_sync_activity")).json()
        self.assertEqual((data["status"], data["kind_label"]), ("queued", "Update check"))
        self.assertContains(self.page(), "Update check queued")
        # The worker picks it up: queued turns into running.
        engine = HollihopSyncEngine(client=self.api)
        engine.activity_kind = "smart"
        engine.acquire_lock()
        self.assertEqual(activity.current()["status"], "running")
        engine.release_lock()
        self.assertEqual(activity.current()["status"], "idle")

    def test_a_full_run_walks_through_the_stages_and_ends_idle(self):
        seen = []
        real_note = activity.note

        def spy(*, stage=None, summary=None):
            if stage:
                seen.append(stage)
            return real_note(stage=stage, summary=summary)

        engine = HollihopSyncEngine(client=self.api)
        with mock.patch.object(activity, "note", side_effect=spy):
            engine.run(stages={"teachers", "students", "classrooms", "memberships"})
        self.assertEqual(seen, ["teachers", "students", "classrooms", "memberships"])
        self.assertEqual(activity.current()["status"], "idle")

    def test_a_crashed_worker_does_not_look_busy_forever(self):
        activity.started("full")
        HollihopSyncState.objects.create(
            provider="hollihop", lock_token="00000000-0000-0000-0000-000000000001",
            lock_expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(activity.current()["status"], "idle")

    def test_dry_runs_never_show_as_running(self):
        engine = HollihopSyncEngine(client=self.api, dry_run=True)
        engine.run(stages={"students"})
        self.assertEqual(activity.current()["status"], "idle")

    def test_only_managers_see_the_status(self):
        kid = User.objects.create_user("v89_kid", password="x")
        self.client.force_login(kid)
        self.assertEqual(self.client.get(reverse("hollihop_sync_activity")).status_code, 403)

    def test_cache_trouble_never_breaks_a_sync(self):
        with mock.patch.object(activity.cache, "set", side_effect=ConnectionError("redis down")), \
                mock.patch.object(activity.cache, "get", side_effect=ConnectionError("redis down")):
            summary = HollihopSyncEngine(client=self.api).run(stages={"teachers", "students"})
            self.assertEqual(summary.errors, 0)
            self.assertEqual(activity.current()["status"], "idle")

"""V73 A-to-Z: manager-side Hollihop actions (sync buttons, conflicts, credential resend, attendance pages)."""
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.integrations.models import HollihopSyncConflict, HollihopSyncState
from apps.sat.models import Classroom

HOLLIHOP_ON = dict(HOLLIHOP_ENABLED=True, SCHOOL_DATA_PROVIDER="hollihop", HOLLIHOP_API_URL="https://hh.invalid/api",
                   HOLLIHOP_AUTH_KEY="test-key")
VIEWS = "apps.integrations.hollihop.views"


def in_group(user, name):
    user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


class HollihopManagerActionsTests(TestCase):
    def setUp(self):
        self.manager = in_group(User.objects.create_user("hh_manager", password="x"), "Manager")
        self.kid = User.objects.create_user("hh_kid", password="x")
        self.client.force_login(self.manager)

    def initial_done(self):
        HollihopSyncState.objects.update_or_create(provider="hollihop", defaults={"initial_sync_completed": True})

    def test_students_and_teachers_cannot_use_any_action(self):
        teacher = in_group(User.objects.create_user("hh_teacher", password="x"), "Teacher")
        conflict = HollihopSyncConflict.objects.create(external_type="student", external_id="501", reason="dup")
        for who in (self.kid, teacher):
            self.client.force_login(who)
            for url in (reverse("hollihop_initial_sync"), reverse("hollihop_smart_sync"), reverse("hollihop_full_reconciliation"),
                        reverse("hollihop_membership_sync"), reverse("hollihop_sync_now"),
                        reverse("hollihop_resend_credentials", args=[self.kid.pk]),
                        reverse("hollihop_resolve_conflict", args=[conflict.pk])):
                self.assertEqual(self.client.post(url, {"confirm": "FULL", "action": "ignore"}).status_code, 403, (who, url))
            self.assertEqual(self.client.get(reverse("hollihop_dashboard")).status_code, 403)
        conflict.refresh_from_db()
        self.assertEqual(conflict.status, "pending")

    def test_sync_buttons_do_nothing_while_hollihop_is_off(self):
        with mock.patch(f"{VIEWS}.manual_full_hollihop_reconciliation") as task:
            response = self.client.post(reverse("hollihop_full_reconciliation"), {"confirm": "FULL"}, follow=True)
        self.assertContains(response, "Hollihop is disabled")
        task.delay.assert_not_called()

    @override_settings(**HOLLIHOP_ON)
    def test_initial_sync_needs_confirmation_and_queues_once(self):
        with mock.patch(f"{VIEWS}.manual_initial_hollihop_sync") as task, mock.patch(f"{VIEWS}.cache") as cache:
            cache.add.side_effect = [True, False]
            self.client.post(reverse("hollihop_initial_sync"), {})
            task.delay.assert_not_called()
            self.client.post(reverse("hollihop_initial_sync"), {"confirm": "INITIAL"})
            self.client.post(reverse("hollihop_initial_sync"), {"confirm": "INITIAL"})  # double click
            self.assertEqual(task.delay.call_count, 1)

    @override_settings(**HOLLIHOP_ON)
    def test_smart_membership_and_full_sync_are_gated_by_the_initial_import(self):
        with mock.patch(f"{VIEWS}.manual_smart_hollihop_sync") as smart, \
                mock.patch(f"{VIEWS}.manual_membership_hollihop_sync") as members, \
                mock.patch(f"{VIEWS}.manual_full_hollihop_reconciliation") as full:
            self.client.post(reverse("hollihop_smart_sync"))
            self.client.post(reverse("hollihop_sync_now"))
            smart.delay.assert_not_called()
            self.initial_done()
            self.client.post(reverse("hollihop_smart_sync"))
            self.client.post(reverse("hollihop_membership_sync"), {"confirm": "nope"})
            self.client.post(reverse("hollihop_membership_sync"), {"confirm": "MEMBERSHIPS"})
            self.client.post(reverse("hollihop_full_reconciliation"), {"confirm": "FULL"})
            self.assertEqual((smart.delay.call_count, members.delay.call_count, full.delay.call_count), (1, 1, 1))

    @override_settings(**HOLLIHOP_ON)
    def test_a_running_sync_blocks_new_ones(self):
        from datetime import timedelta

        from django.utils import timezone
        self.initial_done()
        HollihopSyncState.objects.filter(provider="hollihop").update(lock_token=__import__("uuid").uuid4(), lock_expires_at=timezone.now() + timedelta(minutes=5))
        with mock.patch(f"{VIEWS}.manual_smart_hollihop_sync") as smart:
            response = self.client.post(reverse("hollihop_smart_sync"), follow=True)
        self.assertContains(response, "already running")
        smart.delay.assert_not_called()

    def test_conflicts_ignore_link_and_refuse_duplicates(self):
        ignore = HollihopSyncConflict.objects.create(external_type="student", external_id="601", reason="two matches")
        self.client.post(reverse("hollihop_resolve_conflict", args=[ignore.pk]), {"action": "ignore"})
        ignore.refresh_from_db()
        self.assertEqual(ignore.status, "ignored")

        link = HollihopSyncConflict.objects.create(external_type="student", external_id="602", reason="no email")
        self.client.post(reverse("hollihop_resolve_conflict", args=[link.pk]), {"action": "link", "user_id": "zz"})
        link.refresh_from_db()
        self.assertEqual(link.status, "pending")
        self.client.post(reverse("hollihop_resolve_conflict", args=[link.pk]), {"action": "link", "user_id": self.kid.pk})
        link.refresh_from_db()
        self.kid.profile.refresh_from_db()
        self.assertEqual((link.status, self.kid.profile.hollihop_client_id), ("resolved", 602))

        other = User.objects.create_user("hh_other", password="x")
        other.profile.hollihop_client_id = 700
        other.profile.save()
        dup = HollihopSyncConflict.objects.create(external_type="student", external_id="700", reason="again")
        self.client.post(reverse("hollihop_resolve_conflict", args=[dup.pk]), {"action": "link", "user_id": self.kid.pk})
        dup.refresh_from_db()
        self.assertEqual(dup.status, "pending")  # id 700 already belongs to hh_other
        self.kid.profile.refresh_from_db()
        self.assertEqual(self.kid.profile.hollihop_client_id, 602)

    def test_classroom_conflict_must_be_linked_to_a_teacher(self):
        conflict = HollihopSyncConflict.objects.create(external_type="classroom", external_id="77", reason="no teacher")
        url = reverse("hollihop_resolve_conflict", args=[conflict.pk])
        self.client.post(url, {"action": "link", "user_id": self.kid.pk})
        conflict.refresh_from_db()
        self.assertEqual(conflict.status, "pending")
        teacher = in_group(User.objects.create_user("hh_t2", password="x"), "Teacher")
        with mock.patch(f"{VIEWS}.sync_resolved_classroom_mapping") as task:
            self.client.post(url, {"action": "link", "user_id": teacher.pk})
        conflict.refresh_from_db()
        self.assertEqual((conflict.status, conflict.resolved_user_id), ("resolved", teacher.pk))
        task.delay.assert_called_once_with(77)

    def test_credential_resend_needs_confirmation_and_a_linked_account(self):
        url = reverse("hollihop_resend_credentials", args=[self.kid.pk])
        with mock.patch(f"{VIEWS}.deliver_new_temporary_access") as deliver:
            deliver.return_value = SimpleNamespace(overall_status="sent", get_overall_status_display=lambda: "Sent")
            self.client.post(url, {})                      # no confirmation
            self.client.post(url, {"confirm": "RESET"})    # not linked to Hollihop
            deliver.assert_not_called()
            self.kid.profile.hollihop_client_id = 9001
            self.kid.profile.save()
            self.client.post(url, {"confirm": "RESET"})
            deliver.assert_called_once()

    def test_attendance_pages(self):
        teacher = in_group(User.objects.create_user("hh_t3", password="x"), "Teacher")
        classroom = Classroom.objects.create(teacher=teacher, name="HH class")
        url = reverse("hollihop_classroom_attendance", args=[classroom.pk])
        self.client.force_login(self.kid)
        self.assertEqual(self.client.get(reverse("hollihop_my_attendance")).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 403)
        for who in (teacher, self.manager):
            self.client.force_login(who)
            self.assertEqual(self.client.get(url).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("hollihop_my_attendance")).status_code, 302)

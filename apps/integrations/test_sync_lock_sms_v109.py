"""V109: a restart no longer leaves Hollihop "busy" for 30 minutes; the SMS provider can be checked from the site."""
import socket
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.integrations.hollihop.sms import SmsDeliveryError, SmsSendResult
from apps.integrations.hollihop.sync import (
    HollihopSyncAlreadyRunning, HollihopSyncEngine, lock_is_abandoned, release_locks_of_this_host,
)
from apps.integrations.models import HollihopSyncState


def locked_state(renewed_minutes_ago, owner="other-host"):
    now = timezone.now()
    return HollihopSyncState.objects.create(
        provider="hollihop", lock_token="11111111-1111-1111-1111-111111111111", lock_owner=owner,
        lock_expires_at=now - timedelta(minutes=renewed_minutes_ago) + timedelta(minutes=settings.HOLLIHOP_SYNC_LOCK_MINUTES),
        last_status=HollihopSyncState.STATUS_SYNCING,
    )


class SyncLockTests(TestCase):
    def test_a_live_lock_still_blocks(self):
        locked_state(renewed_minutes_ago=2)
        with self.assertRaises(HollihopSyncAlreadyRunning):
            HollihopSyncEngine(client=mock.Mock()).acquire_lock()

    def test_an_abandoned_lock_is_taken_over(self):
        state = locked_state(renewed_minutes_ago=16)
        self.assertTrue(lock_is_abandoned(state))
        engine = HollihopSyncEngine(client=mock.Mock())
        engine.acquire_lock()
        state.refresh_from_db()
        self.assertEqual(state.lock_token, engine._lock_token)
        self.assertEqual(state.lock_owner, socket.gethostname()[:200])
        engine.release_lock()
        state.refresh_from_db()
        self.assertEqual((state.lock_token, state.lock_owner), (None, ""))

    def test_worker_shutdown_releases_only_its_own_lock(self):
        state = locked_state(renewed_minutes_ago=1, owner=socket.gethostname()[:200])
        from apps.integrations.hollihop.tasks import _release_hollihop_lock_on_shutdown

        _release_hollihop_lock_on_shutdown(sig="SIGTERM", how="warm", exitcode=0)
        state.refresh_from_db()
        self.assertIsNone(state.lock_token)
        self.assertEqual(state.last_status, HollihopSyncState.STATUS_ERROR)
        HollihopSyncEngine(client=mock.Mock()).acquire_lock()  # the next worker syncs at once

    def test_another_hosts_lock_is_untouched(self):
        state = locked_state(renewed_minutes_ago=1, owner="web-container")
        self.assertEqual(release_locks_of_this_host(), 0)
        state.refresh_from_db()
        self.assertIsNotNone(state.lock_token)


class SmsCheckTests(TestCase):
    def setUp(self):
        manager = User.objects.create_user("sms_manager", password="x")
        manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.client.force_login(manager)
        self.url = reverse("hollihop_credential_campaign")

    @override_settings(MAKONBOOK_SMS_PROVIDER="disabled")
    def test_disabled_provider_is_reported(self):
        response = self.client.post(self.url, {"action": "check_sms"}, follow=True)
        self.assertContains(response, "SMS settings: SMS provider is disabled.")

    @override_settings(MAKONBOOK_SMS_PROVIDER="playmobile", PLAYMOBILE_API_URL="https://send.example/api",
                       PLAYMOBILE_LOGIN="login", PLAYMOBILE_PASSWORD="pw", PLAYMOBILE_ORIGINATOR="SATMAKON")
    def test_check_and_test_sms_show_the_provider_answer(self):
        response = self.client.post(self.url, {"action": "check_sms"}, follow=True)
        self.assertContains(response, "PlayMobile configuration is ready. Nothing was sent.")
        with mock.patch("apps.integrations.hollihop.sms.send_sms", side_effect=SmsDeliveryError("PlayMobile rejected the text: not approved")):
            response = self.client.post(self.url, {"action": "sms_test", "phone": "+998901234567"}, follow=True)
        self.assertContains(response, "Test SMS failed: PlayMobile rejected the text: not approved")
        ok = SmsSendResult(provider="playmobile", message_id="mb123", status="accepted")
        with mock.patch("apps.integrations.hollihop.sms.send_sms", return_value=ok) as send:
            response = self.client.post(self.url, {"action": "sms_test", "phone": "+998901234567", "text": "Hello"}, follow=True)
        send.assert_called_once_with("+998901234567", "Hello")
        self.assertContains(response, "Test SMS accepted by playmobile: status accepted, message id mb123")

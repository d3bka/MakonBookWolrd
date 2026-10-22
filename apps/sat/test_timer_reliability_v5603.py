from datetime import timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from .views import _deadline_snapshot_recovery_allowed, _draft_remaining_seconds


class TimerReliabilityV5603Tests(SimpleTestCase):
    def test_fractional_final_second_is_not_treated_as_expired(self):
        draft = SimpleNamespace(deadline_at=timezone.now() + timedelta(milliseconds=900))
        self.assertGreaterEqual(_draft_remaining_seconds(draft), 1)

    def test_near_deadline_frozen_snapshot_can_recover_after_network_delay(self):
        deadline = timezone.now() - timedelta(seconds=1)
        draft = SimpleNamespace(deadline_at=deadline)
        deadline_ms = int(deadline.timestamp() * 1000)
        payload = {
            'deadline_reached': True,
            'client_deadline_at': deadline_ms,
            'client_submitted_at': deadline_ms + 500,
        }
        self.assertTrue(_deadline_snapshot_recovery_allowed(draft, payload))

    def test_snapshot_created_well_after_deadline_is_rejected(self):
        deadline = timezone.now() - timedelta(seconds=1)
        draft = SimpleNamespace(deadline_at=deadline)
        deadline_ms = int(deadline.timestamp() * 1000)
        payload = {
            'deadline_reached': True,
            'client_deadline_at': deadline_ms,
            'client_submitted_at': deadline_ms + 5000,
        }
        self.assertFalse(_deadline_snapshot_recovery_allowed(draft, payload))

    def test_recovery_window_is_not_unbounded(self):
        deadline = timezone.now() - timedelta(seconds=45)
        draft = SimpleNamespace(deadline_at=deadline)
        deadline_ms = int(deadline.timestamp() * 1000)
        payload = {
            'deadline_reached': True,
            'client_deadline_at': deadline_ms,
            'client_submitted_at': deadline_ms,
        }
        self.assertFalse(_deadline_snapshot_recovery_allowed(draft, payload))

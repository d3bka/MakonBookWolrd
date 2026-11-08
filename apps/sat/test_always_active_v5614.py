from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from .models import GlobalEvent, Test


class GlobalEventAlwaysActiveV5614Tests(TestCase):
    def setUp(self):
        self.test = Test.objects.create(name="ALWAYS ACTIVE V5614")

    def make_event(self, **overrides):
        now = timezone.now()
        data = {
            "title": "Always Active V5614",
            "slug": "always-active-v5614",
            "test": self.test,
            "start_at": now + timedelta(days=30),
            "end_at": now - timedelta(days=30),
            "status": "live",
            "is_public": True,
            "always_live": True,
        }
        data.update(overrides)
        return GlobalEvent.objects.create(**data)

    def test_always_active_ignores_past_end_and_future_start(self):
        event = self.make_event()
        self.assertTrue(event.is_live_now)
        self.assertIsNone(event.effective_end_at)

    def test_close_expired_does_not_close_always_active(self):
        event = self.make_event()
        GlobalEvent.close_expired(timezone.now())
        event.refresh_from_db()
        self.assertEqual(event.status, "live")
        self.assertTrue(event.is_live_now)

    def test_manual_closed_status_still_overrides_always_active(self):
        event = self.make_event(status="closed")
        self.assertFalse(event.is_live_now)

    def test_scheduled_event_still_closes_after_grace(self):
        now = timezone.now()
        event = self.make_event(
            slug="scheduled-expired-v5614",
            always_live=False,
            start_at=now - timedelta(days=2),
            end_at=now - timedelta(hours=GlobalEvent.END_GRACE_HOURS, minutes=1),
        )
        GlobalEvent.close_expired(now)
        event.refresh_from_db()
        self.assertEqual(event.status, "closed")
        self.assertFalse(event.is_live_now)

from unittest.mock import patch

from django.test import SimpleTestCase

from apps.telegram_bot import placement_notifications as notices


class FakeBot:
    def __init__(self, failures=None):
        self.failures = set(failures or [])
        self.calls = []

    async def send_message(self, *, chat_id, text):
        self.calls.append(chat_id)
        if chat_id in self.failures:
            raise RuntimeError(f"cannot send to {chat_id}")
        return True


class PlacementTelegramGroupDeliveryV5615Tests(SimpleTestCase):
    def payload(self):
        return {
            "kind": "started",
            "name": "Test Student",
            "phone": "+998901234567",
            "event": "English Placement",
            "lead_id": 1,
            "admin_url": "",
        }

    def test_chat_target_parser_supports_supergroups_and_multiple_targets(self):
        self.assertEqual(
            notices._parse_chat_targets("-1001234567890, -1009876543210, @public_group"),
            [-1001234567890, -1009876543210, "@public_group"],
        )

    async def test_failed_explicit_group_is_not_masked_by_admin_dm(self):
        bot = FakeBot(failures={-100123})
        deliveries = []

        def mark(notification_id, *, success, error=""):
            deliveries.append((notification_id, success, error))

        with (
            patch.object(notices, "_pending_ids", return_value=[1]),
            patch.object(notices, "_destinations", return_value=([-100123], [777])),
            patch.object(notices, "_notification_snapshot", return_value=self.payload()),
            patch.object(notices, "_mark_delivery", side_effect=mark),
        ):
            delivered = await notices.deliver_pending_placement_notifications(bot)

        self.assertEqual(delivered, 0)
        self.assertEqual(bot.calls, [-100123])
        self.assertEqual(deliveries[0][1], False)
        self.assertIn("placement target -100123", deliveries[0][2])

    async def test_group_success_is_primary_and_admin_copy_is_best_effort(self):
        bot = FakeBot(failures={777})
        deliveries = []

        def mark(notification_id, *, success, error=""):
            deliveries.append((notification_id, success, error))

        with (
            patch.object(notices, "_pending_ids", return_value=[1]),
            patch.object(notices, "_destinations", return_value=([-100123], [777])),
            patch.object(notices, "_notification_snapshot", return_value=self.payload()),
            patch.object(notices, "_mark_delivery", side_effect=mark),
        ):
            delivered = await notices.deliver_pending_placement_notifications(bot)

        self.assertEqual(delivered, 1)
        self.assertEqual(bot.calls, [-100123, 777])
        self.assertEqual(deliveries[0][1], True)
        self.assertIn("admin copy 777", deliveries[0][2])

    async def test_admins_remain_fallback_when_no_group_is_configured(self):
        bot = FakeBot()
        deliveries = []

        def mark(notification_id, *, success, error=""):
            deliveries.append((notification_id, success, error))

        with (
            patch.object(notices, "_pending_ids", return_value=[1]),
            patch.object(notices, "_destinations", return_value=([], [777])),
            patch.object(notices, "_notification_snapshot", return_value=self.payload()),
            patch.object(notices, "_mark_delivery", side_effect=mark),
        ):
            delivered = await notices.deliver_pending_placement_notifications(bot)

        self.assertEqual(delivered, 1)
        self.assertEqual(bot.calls, [777])
        self.assertEqual(deliveries[0][1], True)

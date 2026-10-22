from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from apps.sat.models import PlacementTelegramNotification
from apps.telegram_bot import placement_notifications as notices


class ThreadBot:
    def __init__(self, *, edit_failures=None, reply_failures=None):
        self.next_message_id = 1000
        self.sent = []
        self.edits = []
        self.edit_failures = set(edit_failures or [])
        self.reply_failures = set(reply_failures or [])

    async def send_message(self, *, chat_id, text, reply_to_message_id=None, **kwargs):
        if reply_to_message_id in self.reply_failures:
            raise RuntimeError(f"cannot reply to {reply_to_message_id}")
        self.next_message_id += 1
        message = SimpleNamespace(message_id=self.next_message_id)
        self.sent.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_to_message_id": reply_to_message_id,
                "message_id": message.message_id,
            }
        )
        return message

    async def edit_message_text(self, *, chat_id, message_id, text, **kwargs):
        if message_id in self.edit_failures:
            raise RuntimeError(f"cannot edit {message_id}")
        self.edits.append(
            {"chat_id": chat_id, "message_id": message_id, "text": text}
        )
        return True


class PlacementTelegramThreadingV5616Tests(SimpleTestCase):
    chat_id = -5522358410

    def make_payload(self, *, lead_id, attempt_id, kind, telegram_threads=None):
        started = timezone.now() - timedelta(minutes=12)
        payload = {
            "lead_id": lead_id,
            "attempt_id": attempt_id,
            "kind": kind,
            "name": f"Student {lead_id}",
            "phone": "+998901234567",
            "event": "English Placement",
            "started_at": started,
            "completed_at": timezone.now() if kind == "completed" else None,
            "elapsed_minutes": 12 if kind == "completed" else None,
            "admin_url": "",
            "telegram_threads": telegram_threads or {},
        }
        if kind == "completed":
            payload.update(
                {
                    "placement": {"label": "Level 3"},
                    "percentage": 82.5,
                    "raw": 33,
                    "total_questions": 40,
                    "total_score": None,
                    "scoring_label": None,
                }
            )
        return payload

    async def test_four_parallel_attempts_finish_in_their_own_threads(self):
        bot = ThreadBot()
        thread_store = {}
        notice_specs = {}
        notification_ids = []

        # Four students START before any of them FINISHES.
        for index in range(4):
            lead_id = 101 + index
            attempt_id = 2001 + index
            start_notice_id = 1 + index
            finish_notice_id = 11 + index
            notification_ids.append(start_notice_id)
            notice_specs[start_notice_id] = (lead_id, attempt_id, "started")
            notice_specs[finish_notice_id] = (lead_id, attempt_id, "completed")
        notification_ids.extend([11, 12, 13, 14])

        def snapshot(notification_id):
            lead_id, attempt_id, kind = notice_specs[notification_id]
            refs = thread_store.get((lead_id, str(self.chat_id)), {})
            threads = {str(self.chat_id): dict(refs)} if refs else {}
            return self.make_payload(
                lead_id=lead_id,
                attempt_id=attempt_id,
                kind=kind,
                telegram_threads=threads,
            )

        def remember(lead_id, chat_id, field, message_id):
            refs = thread_store.setdefault((lead_id, str(chat_id)), {})
            refs[field] = message_id

        deliveries = []

        def mark(notification_id, *, success, error=""):
            deliveries.append((notification_id, success, error))

        with (
            patch.object(notices, "_pending_ids", return_value=notification_ids),
            patch.object(notices, "_destinations", return_value=([self.chat_id], [])),
            patch.object(notices, "_notification_snapshot", side_effect=snapshot),
            patch.object(notices, "_store_thread_message_id", side_effect=remember),
            patch.object(notices, "_mark_delivery", side_effect=mark),
        ):
            delivered = await notices.deliver_pending_placement_notifications(bot)

        self.assertEqual(delivered, 8)
        self.assertEqual(len(bot.edits), 4)

        starts = [row for row in bot.sent if row["reply_to_message_id"] is None][:4]
        replies = [row for row in bot.sent if row["reply_to_message_id"] is not None]
        self.assertEqual(len(starts), 4)
        self.assertEqual(len(replies), 4)

        start_ids = [row["message_id"] for row in starts]
        self.assertEqual([row["message_id"] for row in bot.edits], start_ids)
        self.assertEqual([row["reply_to_message_id"] for row in replies], start_ids)
        self.assertEqual(len(set(row["reply_to_message_id"] for row in replies)), 4)
        self.assertTrue(all(success for _notice, success, _error in deliveries))

    async def test_deleted_start_message_falls_back_to_full_completion(self):
        start_id = 777
        bot = ThreadBot(edit_failures={start_id})
        payload = self.make_payload(
            lead_id=1,
            attempt_id=99,
            kind=PlacementTelegramNotification.KIND_COMPLETED,
            telegram_threads={str(self.chat_id): {notices.THREAD_START_KEY: start_id}},
        )
        stored = []

        with patch.object(notices, "_store_thread_message_id", side_effect=lambda *args: stored.append(args)):
            ok, errors = await notices._deliver_notice_to_chat(bot, payload, self.chat_id)

        self.assertTrue(ok)
        self.assertTrue(any("completion edit" in error for error in errors))
        self.assertEqual(len(bot.sent), 1)
        self.assertIsNone(bot.sent[0]["reply_to_message_id"])
        self.assertIn("EXAM COMPLETED", bot.sent[0]["text"])
        self.assertEqual(stored[0][2], notices.THREAD_COMPLETION_KEY)

    async def test_existing_completion_message_prevents_duplicate_reply(self):
        bot = ThreadBot()
        payload = self.make_payload(
            lead_id=1,
            attempt_id=99,
            kind=PlacementTelegramNotification.KIND_COMPLETED,
            telegram_threads={
                str(self.chat_id): {
                    notices.THREAD_START_KEY: 700,
                    notices.THREAD_COMPLETION_KEY: 701,
                }
            },
        )

        ok, errors = await notices._deliver_notice_to_chat(bot, payload, self.chat_id)

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(bot.sent, [])
        self.assertEqual(bot.edits, [])

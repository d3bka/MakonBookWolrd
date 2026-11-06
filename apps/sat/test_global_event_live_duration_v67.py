"""V67: admin edits to a live event change currently running module clocks."""
import json
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    English_Question, GlobalEvent, GlobalEventAttempt,
    GlobalEventModuleDraft, GuestParticipant, Test,
)


@override_settings(MAKONBOOK_GUEST_MODE_ENABLED=True)
class GlobalEventLiveDurationV67Tests(TestCase):
    def setUp(self):
        self.test_obj = Test.objects.create(name="V67 LIVE DURATION")
        self.question = English_Question.objects.create(
            test=self.test_obj, module="module_1", number=1,
            passage="Text", question="Choose A", a="A", b="B", c="C", d="D", answer="A",
        )
        now = timezone.now()
        self.event = GlobalEvent.objects.create(
            title="V67 Event", slug="v67-event", test=self.test_obj,
            start_at=now - timedelta(hours=1), end_at=now + timedelta(hours=4),
            status="live", english_duration_minutes=50, math_duration_minutes=50,
            is_public=True,
        )
        self.guest = GuestParticipant.objects.create(full_name="Student V67")
        session = self.client.session
        session["guest_mode"] = True
        session["guest_id"] = str(self.guest.guest_id)
        session.save()
        self.attempt = GlobalEventAttempt.objects.create(
            event=self.event, guest=self.guest, expires_at=now + timedelta(hours=4),
            total_questions=1,
        )
        self.page = reverse("global_event_attempt_root", args=[self.attempt.guest_token])
        self.status = reverse("global_event_submit_status_root", args=[self.attempt.guest_token])
        self.save = reverse("save_global_event_answer_root", args=[self.attempt.guest_token])
        self.submit = reverse("submit_global_event_root", args=[self.attempt.guest_token])
        response = self.client.get(self.page)
        self.assertEqual(response.status_code, 200)
        self.draft = GlobalEventModuleDraft.objects.get(attempt=self.attempt, section="english", module="m1")

    def _status(self):
        return self.client.get(self.status, {"section": "english", "module": "m1"})

    def _admin_duration_update(self, minutes):
        # Model.save is what the ordinary Django Admin change form performs.
        self.event.english_duration_minutes = minutes
        self.event.save(update_fields=["english_duration_minutes", "updated_at"])

    def test_shorten_from_50_to_40_updates_browser_status_and_autosave(self):
        before = self._status().json()
        self.assertEqual(before["state"], "pending")
        self._admin_duration_update(40)
        after = self._status().json()
        self.assertEqual(after["state"], "pending")
        self.assertAlmostEqual(before["deadline_at"] - after["deadline_at"], 600000, delta=1000)
        # V67 uses ceil() to avoid losing the last fractional second.
        # Right after an edit, 40:00 (2400 s) is valid; floor-minutes may
        # therefore show 40 rather than 39. Check the deadline change and
        # actual seconds, not a fragile rounded minute bucket.
        self.assertGreater(after["remaining_seconds"], 39 * 60)
        self.assertLessEqual(after["remaining_seconds"], 40 * 60)
        self.assertAlmostEqual(
            before["remaining_seconds"] - after["remaining_seconds"],
            10 * 60,
            delta=3,
        )
        saved = self.client.post(self.save, json.dumps({
            "section": "english", "module": "m1",
            "answers": [{"questionID": self.question.pk, "answer": "A", "time_spent": 12}],
        }), content_type="application/json")
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["deadline_at"], after["deadline_at"])
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.answers[0]["answer"], "A")

    def test_extension_from_40_to_50_does_not_restart_module(self):
        self._admin_duration_update(40)
        self.client.get(self.page)
        first_deadline = self._status().json()["deadline_at"]
        self._admin_duration_update(50)
        second_deadline = self._status().json()["deadline_at"]
        self.assertAlmostEqual(second_deadline - first_deadline, 600000, delta=1000)
        self.draft.refresh_from_db()
        self.assertEqual(int(self.draft.created_at.timestamp() * 1000) + (50 * 60000), second_deadline)

    def test_if_new_limit_already_elapsed_server_rejects_new_autosave(self):
        started = timezone.now() - timedelta(minutes=45)
        GlobalEventModuleDraft.objects.filter(pk=self.draft.pk).update(created_at=started, deadline_at=started + timedelta(minutes=50))
        self._admin_duration_update(40)
        status = self._status().json()
        self.assertEqual(status["remaining_seconds"], 0)
        response = self.client.post(self.save, json.dumps({
            "section": "english", "module": "m1",
            "answers": [{"questionID": self.question.pk, "answer": "A"}],
        }), content_type="application/json")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()["time_over"])
        self.draft.refresh_from_db()
        self.assertLessEqual(self.draft.deadline_at, timezone.now())

    def test_draft_unchanged_without_admin_event_edit(self):
        manually_adjusted = timezone.now() - timedelta(seconds=10)
        GlobalEventModuleDraft.objects.filter(pk=self.draft.pk).update(deadline_at=manually_adjusted)
        self.client.get(self.status, {"section": "english", "module": "m1"})
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.deadline_at, manually_adjusted)

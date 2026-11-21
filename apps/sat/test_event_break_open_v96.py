"""V96: events pause 10 minutes between subjects (no skip) and open events need no registration."""
import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.sat.models import (
    English_Question, GlobalEvent, GlobalEventAttempt, GlobalEventModuleDraft, GuestParticipant, Math_Question, Test,
)


class EventSetupMixin:
    def make_event(self, slug="v96-event", **extra):
        test = Test.objects.create(name=f"V96 {slug}")
        English_Question.objects.create(test=test, module="module_1", number=1, passage="P", question="Q",
                                        a="A", b="B", c="C", d="D", answer="A")
        Math_Question.objects.create(test=test, module="module_1", number=1, question="M",
                                     a="1", b="2", c="3", d="4", answer="B")
        now = timezone.now()
        values = dict(title="V96 Event", slug=slug, test=test, start_at=now - timedelta(hours=1),
                      end_at=now + timedelta(hours=4), status="live", is_public=True)
        values.update(extra)
        return GlobalEvent.objects.create(**values)

    def start(self, event, **post):
        return self.client.post(reverse("start_global_event_root", args=[event.slug]), post)

    def submit_english(self, attempt):
        page = reverse("global_event_attempt_root", args=[attempt.guest_token])
        self.assertEqual(self.client.get(page).status_code, 200)
        question = English_Question.objects.get(test=attempt.event.test)
        response = self.client.post(
            reverse("submit_global_event_root", args=[attempt.guest_token]),
            json.dumps({"section": "english", "module": "m1",
                        "answers": [{"questionID": question.pk, "answer": "A", "time_spent": 5}]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        return page


class OpenEventWithoutRegistrationTests(EventSetupMixin, TestCase):
    def test_visitor_gives_a_name_and_starts(self):
        event = self.make_event()
        detail = self.client.get(reverse("global_event_detail_root", args=[event.slug]))
        self.assertContains(detail, 'name="full_name"')
        self.assertContains(detail, "Start event")

        response = self.start(event, full_name="  Aziz   Karimov ")
        attempt = GlobalEventAttempt.objects.get(event=event)
        self.assertRedirects(response, reverse("global_event_attempt_root", args=[attempt.guest_token]),
                             fetch_redirect_response=False)
        self.assertEqual(attempt.guest.full_name, "Aziz Karimov")
        self.assertEqual(self.client.get(response.url).status_code, 200)

    def test_name_is_required(self):
        event = self.make_event()
        response = self.start(event)
        self.assertRedirects(response, reverse("global_event_detail_root", args=[event.slug]),
                             fetch_redirect_response=False)
        self.assertFalse(GlobalEventAttempt.objects.exists())
        self.assertFalse(GuestParticipant.objects.exists())

    def test_wrong_access_code_creates_nobody(self):
        event = self.make_event(access_code="SECRET")
        self.start(event, full_name="Aziz", access_code="wrong")
        self.assertFalse(GuestParticipant.objects.exists())
        self.start(event, full_name="Aziz", access_code="secret")
        self.assertEqual(GlobalEventAttempt.objects.count(), 1)

    def test_second_start_resumes_the_same_attempt(self):
        event = self.make_event()
        self.start(event, full_name="Aziz")
        self.start(event)
        self.assertEqual(GlobalEventAttempt.objects.count(), 1)
        detail = self.client.get(reverse("global_event_detail_root", args=[event.slug]))
        self.assertContains(detail, "Resume attempt")

    def test_registration_event_still_requires_registration(self):
        now = timezone.now()
        event = self.make_event(registration_enabled=True, capacity=10, branch="NOVZA",
                                registration_opens_at=now - timedelta(days=1),
                                registration_closes_at=now + timedelta(days=1))
        response = self.start(event, full_name="Aziz")
        self.assertRedirects(response, reverse("event_registration_choice", args=[event.slug]),
                             fetch_redirect_response=False)
        self.assertFalse(GlobalEventAttempt.objects.exists())

    def test_signed_in_student_needs_no_name(self):
        event = self.make_event()
        self.client.force_login(User.objects.create_user("v96_student", password="x"))
        self.start(event)
        self.assertEqual(GlobalEventAttempt.objects.count(), 1)


class EventSubjectBreakTests(EventSetupMixin, TestCase):
    def setUp(self):
        self.event = self.make_event()
        self.start(self.event, full_name="Malika")
        self.attempt = GlobalEventAttempt.objects.get()

    def test_break_after_reading_and_writing_cannot_be_skipped(self):
        page = self.submit_english(self.attempt)
        self.attempt.refresh_from_db()
        self.assertIsNotNone(self.attempt.subject_break_until)
        left = (self.attempt.subject_break_until - timezone.now()).total_seconds()
        self.assertGreater(left, 9 * 60)

        response = self.client.get(page)
        self.assertTemplateUsed(response, "test/scheduled_break.html")
        self.assertContains(response, "Take a break before Mathematics")
        self.assertContains(response, 'data-auto-continue="1"')
        self.assertNotContains(response, "Skip break")
        # The practice-test skip parameter does nothing here.
        response = self.client.get(page + "?skip_break=1")
        self.assertTemplateUsed(response, "test/scheduled_break.html")
        self.assertFalse(GlobalEventModuleDraft.objects.filter(attempt=self.attempt, section="math").exists())
        # Saving or submitting Math during the break is refused.
        submit = self.client.post(reverse("submit_global_event_root", args=[self.attempt.guest_token]),
                                  json.dumps({"section": "math", "module": "m1", "answers": []}),
                                  content_type="application/json")
        self.assertNotEqual(submit.status_code, 200)

    def test_math_opens_when_the_break_is_over_with_its_full_time(self):
        page = self.submit_english(self.attempt)
        GlobalEventAttempt.objects.filter(pk=self.attempt.pk).update(
            subject_break_until=timezone.now() - timedelta(seconds=1))
        response = self.client.get(page)
        self.assertTemplateUsed(response, "sat/guest/attempt_math.html")
        draft = GlobalEventModuleDraft.objects.get(attempt=self.attempt, section="math", module="m1")
        left = (draft.deadline_at - timezone.now()).total_seconds()
        self.assertGreater(left, (self.event.math_duration_minutes - 1) * 60)
        self.attempt.refresh_from_db()
        self.assertIsNone(self.attempt.subject_break_until)

    def test_placement_tests_have_no_break(self):
        placement = self.make_event(slug="v96-placement", event_type=GlobalEvent.TYPE_PLACEMENT)
        self.start(placement)
        attempt = GlobalEventAttempt.objects.get(event=placement)
        page = self.submit_english(attempt)
        attempt.refresh_from_db()
        self.assertIsNone(attempt.subject_break_until)
        self.assertTemplateUsed(self.client.get(page), "sat/guest/attempt_math.html")


class PracticeBreakStillSkippableTests(TestCase):
    def test_practice_break_page_keeps_skip(self):
        from django.template.loader import render_to_string

        html = render_to_string("test/scheduled_break.html", {
            "test": {"name": "DAY1"}, "break_remaining_seconds": 600, "continue_url": "/x/",
            "skip_break_url": "/x/?skip_break=1", "next_section_label": "Mathematics",
        })
        self.assertIn("Skip break", html)
        self.assertNotIn("data-auto-continue", html)

"""V50.5 Mako: rule-based study companion on the student Home."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.gamification.mako import (
    STATE_CELEBRATE, STATE_FOCUS, STATE_IDLE, STATE_NUDGE, STATE_WELCOME, mako_state,
)

NOW = timezone.make_aware(timezone.datetime(2026, 11, 14, 12, 0))
CONFIGURED = SimpleNamespace(is_configured=True)


def xp_event(amount, when=NOW):
    return SimpleNamespace(amount=amount, created_at=when)


def gamification(**overrides):
    base = {
        "level": 1, "level_title": "Starter", "xp_total": 0, "level_floor_xp": 0,
        "current_streak": 0, "daily_total": 2, "daily_completed": 0, "recent_events": [],
    }
    base.update(overrides)
    return base


def state(**kwargs):
    kwargs.setdefault("goal", CONFIGURED)
    kwargs.setdefault("has_classroom", True)
    kwargs.setdefault("now", NOW)
    return mako_state(**kwargs)


class MakoRuleTests(SimpleTestCase):
    def test_level_up_today_is_celebrated(self):
        result = state(gamification=gamification(level=3, level_title="Builder", xp_total=320, level_floor_xp=300,
                                                 recent_events=[xp_event(40)]))
        self.assertEqual(result["state"], STATE_CELEBRATE)
        self.assertEqual(result["event"], "level-3")
        self.assertIn("Level 3", result["headline"])

    def test_old_level_is_not_celebrated_again(self):
        yesterday = NOW - timedelta(days=1)
        result = state(gamification=gamification(level=3, xp_total=320, level_floor_xp=300,
                                                 recent_events=[xp_event(40, yesterday)]))
        self.assertNotEqual(result["state"], STATE_CELEBRATE)

    def test_deadline_within_24h_nudges_and_is_first_step(self):
        due = [{"title": "Unit 4 quiz", "url": "/homework/9/", "meta": "Nov 15", "due_at": NOW + timedelta(hours=5)}]
        result = state(gamification=gamification(), due_items=due)
        self.assertEqual(result["state"], STATE_NUDGE)
        self.assertEqual(result["recommendations"][0]["url"], "/homework/9/")
        self.assertIn("Unit 4 quiz", result["message"])

    def test_far_deadline_is_a_step_but_not_a_nudge(self):
        due = [{"title": "Essay", "url": "/homework/3/", "meta": "Nov 30", "due_at": NOW + timedelta(days=10)}]
        result = state(gamification=gamification(), due_items=due)
        self.assertNotEqual(result["state"], STATE_NUDGE)
        self.assertEqual(result["recommendations"][0]["kind"], "deadline")

    def test_all_daily_quests_done_celebrates(self):
        result = state(gamification=gamification(daily_completed=2, recent_events=[xp_event(10)]))
        self.assertEqual(result["state"], STATE_CELEBRATE)
        self.assertTrue(result["event"].startswith("quests-"))

    def test_streak_at_risk_when_inactive_today(self):
        result = state(gamification=gamification(current_streak=5))
        self.assertEqual(result["state"], STATE_NUDGE)
        self.assertIn("5-day streak", result["headline"])

    def test_streak_safe_once_active_today(self):
        result = state(gamification=gamification(current_streak=5, recent_events=[xp_event(5)]))
        self.assertEqual(result["state"], STATE_IDLE)
        self.assertIn("5 XP", result["message"])

    def test_weak_topic_needs_enough_answers(self):
        noisy = [{"name": "Circles", "section": "math", "total": 2, "wrong": 2, "accuracy": 0}]
        self.assertNotEqual(state(gamification=gamification(), weak_topics=noisy)["state"], STATE_FOCUS)
        real = [{"name": "Circles", "section": "math", "total": 8, "wrong": 5, "accuracy": 38}]
        result = state(gamification=gamification(), weak_topics=real)
        self.assertEqual(result["state"], STATE_FOCUS)
        step = next(r for r in result["recommendations"] if r["kind"] == "weak_topic")
        self.assertIn("38% correct over 8 Math answers", step["reason"])

    def test_new_student_is_welcomed_with_onboarding_steps(self):
        result = mako_state(gamification=gamification(), goal=SimpleNamespace(is_configured=False),
                            has_classroom=False, now=NOW)
        self.assertEqual(result["state"], STATE_WELCOME)
        kinds = [r["kind"] for r in result["recommendations"]]
        self.assertIn("goal", kinds)
        self.assertIn("classroom", kinds)

    def test_at_most_three_unique_steps(self):
        due = [{"title": f"HW {i}", "url": f"/hw/{i}/", "meta": "", "due_at": None} for i in range(4)]
        weak = [{"name": "Lines", "section": "math", "total": 9, "accuracy": 40}]
        result = mako_state(gamification=gamification(), due_items=due, weak_topics=weak,
                            vocabulary={"learning_words": 4}, goal=SimpleNamespace(is_configured=False),
                            has_classroom=False, now=NOW)
        urls = [r["url"] for r in result["recommendations"]]
        self.assertEqual(len(urls), 3)
        self.assertEqual(len(set(urls)), 3)

    def test_never_claims_ai_or_invents_scores(self):
        texts = []
        for kwargs in (
            {"gamification": gamification(current_streak=3)},
            {"gamification": gamification(), "weak_topics": [{"name": "X", "section": "english", "total": 5, "accuracy": 20}]},
            {"gamification": gamification(level=2, xp_total=120, level_floor_xp=100, recent_events=[xp_event(30)])},
        ):
            result = state(**kwargs)
            texts += [result["headline"], result["message"]] + [r["reason"] for r in result["recommendations"]]
        joined = " ".join(texts).lower()
        for banned in ("ai ", "artificial", "predict", "guarantee"):
            self.assertNotIn(banned, joined)


class MakoHomeIntegrationTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user("mako-student", password="x", first_name="Aziz")

    def test_student_home_greets_with_mako_in_the_header(self):
        # V70: Mako moved from a dashboard card (which sank to the bottom of saved
        # layouts) into the "Welcome back" header, as the panda with a speech bubble.
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard_root"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-dashboard-widget="mako"')
        self.assertContains(response, "data-mako-state=")
        self.assertContains(response, "data-mako-hello-panda")
        self.assertContains(response, 'class="mk70-say"')
        self.assertContains(response, "mako-v505.js")
        self.assertContains(response, "mascot-v70.js")

    def test_mako_adds_no_database_queries(self):
        self.client.force_login(self.student)
        self.client.get(reverse("student_dashboard_root"))  # warm one-time session/profile writes
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as with_mako:
            self.client.get(reverse("student_dashboard_root"))
        with patch("apps.gamification.mako.mako_state", return_value=None):
            with CaptureQueriesContext(connection) as without_mako:
                self.client.get(reverse("student_dashboard_root"))
        self.assertEqual(len(with_mako), len(without_mako))

    def test_staff_never_get_mako(self):
        teacher = User.objects.create_user("mako-teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.client.force_login(teacher)
        response = self.client.get(reverse("student_dashboard_root"), follow=True)
        self.assertNotContains(response, "data-mako")
        self.assertNotContains(response, "mascot-v70.js")

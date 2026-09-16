from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.sat.models import VocabularyDeck, VocabularyDeckWord, VocabularyDeckWordProgress

from .models import GamificationProfile, QuestProgress, UserAchievement, XPEvent
from .services import (
    award_xp,
    ensure_current_quests,
    ensure_gamification_profile,
    gamification_context,
    level_snapshot,
    record_learning_activity,
    record_vocabulary_review,
    touch_activity,
)


class GamificationCoreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="v52_student", password="pass123")
        self.deck = VocabularyDeck.objects.create(owner=self.user, title="V52 words")
        self.words = [
            VocabularyDeckWord.objects.create(deck=self.deck, word=f"word-{index}", meaning="meaning", order=index)
            for index in range(1, 121)
        ]

    def test_level_curve_is_deterministic_and_named(self):
        self.assertEqual(level_snapshot(0)["level"], 1)
        self.assertEqual(level_snapshot(99)["level"], 1)
        self.assertEqual(level_snapshot(100)["level"], 2)
        self.assertEqual(level_snapshot(300)["level"], 3)
        self.assertEqual(level_snapshot(1000)["level"], 5)
        self.assertEqual(level_snapshot(1000)["level_title"], "Scholar")

    def test_current_quests_are_curated_three_daily_three_weekly(self):
        daily, weekly = ensure_current_quests(self.user)
        self.assertEqual(len(daily), 3)
        self.assertEqual(len(weekly), 3)
        self.assertTrue(all(row.period_type == QuestProgress.PERIOD_DAILY for row in daily))
        self.assertTrue(all(row.period_type == QuestProgress.PERIOD_WEEKLY for row in weekly))
        self.assertEqual({row.code for row in daily}, {
            "daily_learning_action_5",
            "daily_vocab_review_10",
            "daily_vocab_master_3",
        })

    def test_bootstrap_converts_existing_vocab_progress_once(self):
        VocabularyDeckWordProgress.objects.create(
            user=self.user,
            word=self.words[0],
            status=VocabularyDeckWordProgress.STATUS_LEARNING,
            times_seen=1,
            last_reviewed_at=timezone.now(),
        )
        VocabularyDeckWordProgress.objects.create(
            user=self.user,
            word=self.words[1],
            status=VocabularyDeckWordProgress.STATUS_MASTERED,
            times_seen=2,
            last_reviewed_at=timezone.now(),
            mastered_at=timezone.now(),
        )
        profile = ensure_gamification_profile(self.user)
        self.assertEqual(profile.xp_total, 20)
        self.assertEqual(XPEvent.objects.filter(user=self.user, source_key="bootstrap:v1").count(), 1)
        ensure_gamification_profile(self.user)
        self.assertEqual(GamificationProfile.objects.get(user=self.user).xp_total, 20)

    def test_vocab_xp_and_quest_rewards_are_idempotent(self):
        ensure_gamification_profile(self.user)
        for word in self.words[:10]:
            record_vocabulary_review(
                self.user,
                object_key=f"deckword:{word.id}",
                previous_status="new",
                new_status="learning",
                outcome="known",
            )
        record_vocabulary_review(
            self.user,
            object_key=f"deckword:{self.words[0].id}",
            previous_status="new",
            new_status="learning",
            outcome="known",
        )
        profile = GamificationProfile.objects.get(user=self.user)
        # 10*5 base + 30 daily activity + 40 daily review.
        self.assertEqual(profile.xp_total, 120)
        daily = QuestProgress.objects.get(user=self.user, code="daily_vocab_review_10", period_start=timezone.localdate())
        self.assertEqual(daily.progress, 10)
        self.assertIsNotNone(daily.completed_at)
        self.assertIsNotNone(daily.rewarded_at)
        self.assertEqual(XPEvent.objects.filter(user=self.user, source_key__startswith="quest:").count(), 2)

    def test_central_learning_activity_is_retry_safe(self):
        ensure_gamification_profile(self.user)
        payload = {
            "activity_key": "sat-question:77",
            "metrics": ("custom_metric",),
            "xp_awards": ({
                "amount": 20,
                "source_key": "sat:question:77",
                "title": "Solved a practice question",
            },),
        }
        record_learning_activity(self.user, **payload)
        record_learning_activity(self.user, **payload)
        profile = GamificationProfile.objects.get(user=self.user)
        self.assertEqual(profile.xp_total, 20)
        daily = QuestProgress.objects.get(user=self.user, code="daily_learning_action_5", period_start=timezone.localdate())
        weekly = QuestProgress.objects.get(user=self.user, code="weekly_learning_action_25")
        self.assertEqual(daily.progress, 1)
        self.assertEqual(weekly.progress, 1)

    def test_streak_rolls_forward_and_old_activity_never_rewinds_it(self):
        ensure_gamification_profile(self.user)
        today = timezone.localdate()
        profile = GamificationProfile.objects.get(user=self.user)
        profile.last_active_date = today - timedelta(days=1)
        profile.current_streak = 4
        profile.best_streak = 4
        profile.save(update_fields=["last_active_date", "current_streak", "best_streak"])

        touch_activity(self.user, activity_date=today)
        touch_activity(self.user, activity_date=today - timedelta(days=5))
        profile.refresh_from_db()
        self.assertEqual(profile.current_streak, 5)
        self.assertEqual(profile.best_streak, 5)
        self.assertEqual(profile.last_active_date, today)

    def test_stale_current_streak_expires_on_read_but_best_is_preserved(self):
        ensure_gamification_profile(self.user)
        profile = GamificationProfile.objects.get(user=self.user)
        profile.last_active_date = timezone.localdate() - timedelta(days=3)
        profile.current_streak = 8
        profile.best_streak = 12
        profile.save(update_fields=["last_active_date", "current_streak", "best_streak"])
        refreshed = ensure_gamification_profile(self.user)
        self.assertEqual(refreshed.current_streak, 0)
        self.assertEqual(refreshed.best_streak, 12)

    def test_award_xp_is_idempotent_and_unlocks_xp_achievement(self):
        ensure_gamification_profile(self.user)
        award_xp(self.user, amount=500, source_key="manual:test:500", title="Test milestone")
        award_xp(self.user, amount=500, source_key="manual:test:500", title="Test milestone")
        profile = GamificationProfile.objects.get(user=self.user)
        self.assertEqual(profile.xp_total, 500)
        self.assertTrue(UserAchievement.objects.filter(user=self.user, code="xp_500").exists())

    def test_mastery_unlocks_streak_and_vocab_achievements(self):
        ensure_gamification_profile(self.user)
        profile = GamificationProfile.objects.get(user=self.user)
        profile.last_active_date = timezone.localdate() - timedelta(days=1)
        profile.current_streak = 2
        profile.best_streak = 2
        profile.save(update_fields=["last_active_date", "current_streak", "best_streak"])
        for word in self.words[:10]:
            VocabularyDeckWordProgress.objects.create(
                user=self.user,
                word=word,
                status=VocabularyDeckWordProgress.STATUS_MASTERED,
                times_seen=2,
                mastered_at=timezone.now(),
                last_reviewed_at=timezone.now(),
            )
        record_vocabulary_review(
            self.user,
            object_key=f"deckword:{self.words[0].id}",
            previous_status="learning",
            new_status="mastered",
            outcome="known",
        )
        self.assertTrue(UserAchievement.objects.filter(user=self.user, code="streak_3").exists())
        self.assertTrue(UserAchievement.objects.filter(user=self.user, code="vocab_10").exists())

    def test_quest_achievement_counts_completed_period_rows(self):
        ensure_gamification_profile(self.user)
        now = timezone.now()
        for offset in range(5):
            QuestProgress.objects.create(
                user=self.user,
                code=f"historic_{offset}",
                title="Historic quest",
                period_type=QuestProgress.PERIOD_DAILY,
                period_start=timezone.localdate() - timedelta(days=offset + 1),
                progress=1,
                target=1,
                completed_at=now,
                rewarded_at=now,
            )
        # Any new XP write runs achievement evaluation centrally.
        award_xp(self.user, amount=1, source_key="trigger:quest-achievement", title="Trigger")
        self.assertTrue(UserAchievement.objects.filter(user=self.user, code="quests_5").exists())

    def test_full_context_exposes_professional_progress_metadata(self):
        ensure_gamification_profile(self.user)
        context = gamification_context(self.user)["gamification"]
        self.assertEqual(context["daily_total"], 3)
        self.assertEqual(context["weekly_total"], 3)
        self.assertEqual(context["quest_catalog_size"], 6)
        self.assertIn("level_title", context)
        self.assertEqual(context["achievement_total"], 13)
        self.assertTrue(all("percent" in item for item in context["achievement_catalog"]))

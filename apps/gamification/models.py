from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class GamificationProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="gamification_profile")
    xp_total = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    best_streak = models.PositiveIntegerField(default=0)
    last_active_date = models.DateField(blank=True, null=True)
    bootstrap_version = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} · {self.xp_total} XP"


class XPEvent(models.Model):
    KIND_ACTIVITY = "activity"
    KIND_QUEST = "quest"
    KIND_BOOTSTRAP = "bootstrap"
    KIND_CHOICES = (
        (KIND_ACTIVITY, "Activity"),
        (KIND_QUEST, "Quest reward"),
        (KIND_BOOTSTRAP, "Bootstrap"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="gamification_xp_events")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default=KIND_ACTIVITY)
    source_key = models.CharField(max_length=160)
    title = models.CharField(max_length=180)
    amount = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "source_key"], name="unique_gamification_xp_source"),
        ]
        indexes = [
            models.Index(fields=["user", "created_at"], name="gamification_xp_user_date"),
        ]

    def __str__(self):
        return f"{self.user.username} · +{self.amount} XP · {self.title}"


class QuestProgress(models.Model):
    PERIOD_DAILY = "daily"
    PERIOD_WEEKLY = "weekly"
    PERIOD_CHOICES = (
        (PERIOD_DAILY, "Daily"),
        (PERIOD_WEEKLY, "Weekly"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="gamification_quests")
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=180)
    period_type = models.CharField(max_length=12, choices=PERIOD_CHOICES)
    period_start = models.DateField(db_index=True)
    progress = models.PositiveIntegerField(default=0)
    target = models.PositiveIntegerField(default=1)
    reward_xp = models.PositiveIntegerField(default=0)
    seen_keys = models.JSONField(default=list, blank=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    rewarded_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["period_type", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "code", "period_start"],
                name="unique_gamification_quest_period",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "period_type", "period_start"], name="gamification_quest_user_period"),
        ]

    @property
    def percent(self):
        if not self.target:
            return 100
        return min(100, round((self.progress / self.target) * 100))

    @property
    def is_complete(self):
        return bool(self.completed_at)

    def __str__(self):
        return f"{self.user.username} · {self.title} · {self.progress}/{self.target}"


class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="gamification_achievements")
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=140)
    description = models.CharField(max_length=300)
    icon = models.CharField(max_length=40, default="bi-trophy")
    unlocked_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-unlocked_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "code"], name="unique_gamification_achievement"),
        ]

    def __str__(self):
        return f"{self.user.username} · {self.title}"

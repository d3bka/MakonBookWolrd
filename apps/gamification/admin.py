from django.contrib import admin

from .models import GamificationProfile, QuestProgress, UserAchievement, XPEvent


@admin.register(GamificationProfile)
class GamificationProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "xp_total", "current_streak", "best_streak", "last_active_date", "bootstrap_version")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(XPEvent)
class XPEventAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "kind", "title", "source_key", "created_at")
    list_filter = ("kind", "created_at")
    search_fields = ("user__username", "title", "source_key")
    readonly_fields = ("created_at",)


@admin.register(QuestProgress)
class QuestProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "period_type", "period_start", "progress", "target", "reward_xp", "completed_at")
    list_filter = ("period_type", "period_start", "completed_at")
    search_fields = ("user__username", "title", "code")
    readonly_fields = ("created_at", "updated_at", "completed_at", "rewarded_at")


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "code", "unlocked_at")
    search_fields = ("user__username", "title", "code")
    readonly_fields = ("unlocked_at",)

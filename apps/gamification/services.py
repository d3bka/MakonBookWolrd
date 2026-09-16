from __future__ import annotations

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import GamificationProfile, QuestProgress, UserAchievement, XPEvent


BOOTSTRAP_VERSION = 1

# V50.2 final quest set. Keep the active list deliberately small and legible:
# three daily objectives and three weekly objectives. Future features can feed
# the generic ``learning_action`` metric without adding dashboard clutter.
DAILY_QUESTS = (
    {
        "code": "daily_learning_action_5",
        "title": "Complete 5 learning activities",
        "metric": "learning_action",
        "target": 5,
        "reward_xp": 30,
    },
    {
        "code": "daily_vocab_review_10",
        "title": "Review 10 vocabulary cards",
        "metric": "vocab_review",
        "target": 10,
        "reward_xp": 40,
    },
    {
        "code": "daily_vocab_master_3",
        "title": "Master 3 vocabulary words",
        "metric": "vocab_mastered",
        "target": 3,
        "reward_xp": 60,
    },
)

WEEKLY_QUESTS = (
    {
        "code": "weekly_learning_action_25",
        "title": "Complete 25 learning activities",
        "metric": "learning_action",
        "target": 25,
        "reward_xp": 90,
    },
    {
        "code": "weekly_vocab_review_50",
        "title": "Review 50 vocabulary cards",
        "metric": "vocab_review",
        "target": 50,
        "reward_xp": 120,
    },
    {
        "code": "weekly_vocab_master_15",
        "title": "Master 15 vocabulary words",
        "metric": "vocab_mastered",
        "target": 15,
        "reward_xp": 180,
    },
)

# Kept for backwards imports from older V50.2 code. The rotating 56-quest
# catalogue was intentionally removed: it created different labels for the same
# vocabulary counters without creating meaningful product depth.
QUEST_LIBRARY = ()

LEVEL_TITLES = (
    (1, "Starter"),
    (3, "Learner"),
    (5, "Scholar"),
    (8, "Strategist"),
    (12, "Specialist"),
    (18, "Expert"),
    (25, "Master"),
)


def _achievement(code, title, description, icon, progress_key, target):
    return {
        "code": code,
        "title": title,
        "description": description,
        "icon": icon,
        "progress_key": progress_key,
        "target": target,
        "check": lambda state, key=progress_key, goal=target: state.get(key, 0) >= goal,
    }


ACHIEVEMENTS = (
    _achievement("first_xp", "First Step", "Earn your first MakonBook XP.", "bi-stars", "xp_total", 1),
    _achievement("xp_500", "Momentum", "Earn 500 MakonBook XP.", "bi-lightning-charge", "xp_total", 500),
    _achievement("xp_1000", "Four Digits", "Earn 1,000 MakonBook XP.", "bi-graph-up-arrow", "xp_total", 1000),
    _achievement("level_5", "Scholar", "Reach MakonBook Level 5.", "bi-mortarboard", "level", 5),
    _achievement("level_10", "Double Digits", "Reach MakonBook Level 10.", "bi-rocket-takeoff", "level", 10),
    _achievement("streak_3", "Three-Day Spark", "Stay active for 3 days in a row.", "bi-fire", "best_streak", 3),
    _achievement("streak_7", "Week Warrior", "Stay active for 7 days in a row.", "bi-calendar2-check", "best_streak", 7),
    _achievement("streak_30", "Month of Momentum", "Reach a 30-day learning streak.", "bi-calendar2-heart", "best_streak", 30),
    _achievement("vocab_10", "Word Builder", "Master 10 vocabulary words.", "bi-journal-bookmark", "mastered_words", 10),
    _achievement("vocab_50", "Lexicon Builder", "Master 50 vocabulary words.", "bi-journals", "mastered_words", 50),
    _achievement("vocab_100", "Century of Words", "Master 100 vocabulary words.", "bi-bookmark-star", "mastered_words", 100),
    _achievement("quests_5", "Quest Habit", "Complete 5 MakonBook quests.", "bi-check2-square", "completed_quests", 5),
    _achievement("quests_25", "Quest Regular", "Complete 25 MakonBook quests.", "bi-patch-check", "completed_quests", 25),
)


def _level_floor(level: int) -> int:
    level = max(1, int(level))
    return 50 * (level - 1) * level


def level_title(level: int) -> str:
    level = max(1, int(level or 1))
    title = LEVEL_TITLES[0][1]
    for floor, candidate in LEVEL_TITLES:
        if level < floor:
            break
        title = candidate
    return title


def level_snapshot(xp_total: int) -> dict:
    xp_total = max(0, int(xp_total or 0))
    level = 1
    while xp_total >= _level_floor(level + 1):
        level += 1

    floor_xp = _level_floor(level)
    next_xp = _level_floor(level + 1)
    span = max(1, next_xp - floor_xp)
    into_level = xp_total - floor_xp
    return {
        "level": level,
        "level_title": level_title(level),
        "xp_total": xp_total,
        "level_floor_xp": floor_xp,
        "next_level_xp": next_xp,
        "xp_into_level": into_level,
        "xp_for_next_level": span,
        "xp_remaining": max(0, next_xp - xp_total),
        "level_percent": min(100, round((into_level / span) * 100)),
    }


def _week_start(day):
    return day - timedelta(days=day.weekday())


def _quest_definitions(period_type, period_start=None):
    del period_start  # definitions are stable; period_start remains part of persistence.
    return DAILY_QUESTS if period_type == QuestProgress.PERIOD_DAILY else WEEKLY_QUESTS


def _ensure_quests(user, period_type, period_start):
    definitions = _quest_definitions(period_type, period_start)
    codes = [definition["code"] for definition in definitions]
    existing = {
        row.code: row
        for row in QuestProgress.objects.filter(
            user=user,
            period_start=period_start,
            code__in=codes,
        )
    }

    missing = [definition for definition in definitions if definition["code"] not in existing]
    if missing:
        QuestProgress.objects.bulk_create(
            [
                QuestProgress(
                    user=user,
                    code=definition["code"],
                    period_start=period_start,
                    title=definition["title"],
                    period_type=period_type,
                    target=definition["target"],
                    reward_xp=definition["reward_xp"],
                )
                for definition in missing
            ],
            ignore_conflicts=True,
        )
        existing = {
            row.code: row
            for row in QuestProgress.objects.filter(
                user=user,
                period_start=period_start,
                code__in=codes,
            )
        }

    rows = []
    dirty = []
    now = timezone.now()
    for definition in definitions:
        row = existing.get(definition["code"])
        if row is None:
            row, _ = QuestProgress.objects.get_or_create(
                user=user,
                code=definition["code"],
                period_start=period_start,
                defaults={
                    "title": definition["title"],
                    "period_type": period_type,
                    "target": definition["target"],
                    "reward_xp": definition["reward_xp"],
                },
            )
        if not row.completed_at:
            changed = False
            current_config = {**definition, "period_type": period_type}
            for field in ("title", "target", "reward_xp", "period_type"):
                expected = current_config[field]
                if getattr(row, field) != expected:
                    setattr(row, field, expected)
                    changed = True
            if changed:
                row.updated_at = now
                dirty.append(row)
        rows.append(row)

    if dirty:
        QuestProgress.objects.bulk_update(
            dirty,
            ["title", "target", "reward_xp", "period_type", "updated_at"],
        )
    return rows


def ensure_current_quests(user):
    today = timezone.localdate()
    daily = _ensure_quests(user, QuestProgress.PERIOD_DAILY, today)
    weekly = _ensure_quests(user, QuestProgress.PERIOD_WEEKLY, _week_start(today))
    return daily, weekly


def _active_dates_for_user(user):
    from apps.sat.models import VocabularyDeckWordProgress, VocabularyWordProgress

    dates = set(
        VocabularyDeckWordProgress.objects.filter(
            user=user,
            last_reviewed_at__isnull=False,
        ).values_list("last_reviewed_at__date", flat=True)
    )
    dates.update(
        VocabularyWordProgress.objects.filter(
            user=user,
            last_reviewed_at__isnull=False,
        ).values_list("last_reviewed_at__date", flat=True)
    )
    return dates


def _streak_from_dates(active_dates, today=None):
    today = today or timezone.localdate()
    if not active_dates:
        return 0
    cursor = today if today in active_dates else today - timedelta(days=1)
    streak = 0
    while cursor in active_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _mastered_word_count(user):
    from apps.sat.models import VocabularyDeckWordProgress, VocabularyWordProgress

    return (
        VocabularyDeckWordProgress.objects.filter(user=user, status=VocabularyDeckWordProgress.STATUS_MASTERED).count()
        + VocabularyWordProgress.objects.filter(user=user, status=VocabularyWordProgress.STATUS_MASTERED).count()
    )


def _completed_quest_count(user):
    return QuestProgress.objects.filter(user=user, completed_at__isnull=False).count()


def _bootstrap_xp(user):
    from apps.sat.models import VocabularyDeckWordProgress, VocabularyWordProgress

    deck_counts = VocabularyDeckWordProgress.objects.filter(user=user).aggregate(
        learning=Count("id", filter=Q(status=VocabularyDeckWordProgress.STATUS_LEARNING)),
        mastered=Count("id", filter=Q(status=VocabularyDeckWordProgress.STATUS_MASTERED)),
    )
    unit_counts = VocabularyWordProgress.objects.filter(user=user).aggregate(
        learning=Count("id", filter=Q(status=VocabularyWordProgress.STATUS_LEARNING)),
        mastered=Count("id", filter=Q(status=VocabularyWordProgress.STATUS_MASTERED)),
    )
    learning = int(deck_counts.get("learning") or 0) + int(unit_counts.get("learning") or 0)
    mastered = int(deck_counts.get("mastered") or 0) + int(unit_counts.get("mastered") or 0)
    return (learning * 5) + (mastered * 15)


def _reconcile_streak(profile, *, today=None):
    """Expire stale current streaks without touching historical best streaks."""
    today = today or timezone.localdate()
    last = profile.last_active_date
    if not last:
        return profile
    if last < today - timedelta(days=1) and profile.current_streak:
        profile.current_streak = 0
        profile.save(update_fields=["current_streak", "updated_at"])
    return profile


def ensure_gamification_profile(user):
    profile, _ = GamificationProfile.objects.get_or_create(user=user)
    if profile.bootstrap_version >= BOOTSTRAP_VERSION:
        return _reconcile_streak(profile)

    with transaction.atomic():
        profile = GamificationProfile.objects.select_for_update().get(pk=profile.pk)
        if profile.bootstrap_version >= BOOTSTRAP_VERSION:
            return _reconcile_streak(profile)

        bootstrap_xp = _bootstrap_xp(user)
        dates = _active_dates_for_user(user)
        current_streak = _streak_from_dates(dates)
        profile.xp_total = bootstrap_xp
        profile.current_streak = current_streak
        profile.best_streak = max(profile.best_streak, current_streak)
        profile.last_active_date = max(dates) if dates else None
        profile.bootstrap_version = BOOTSTRAP_VERSION
        profile.save(update_fields=[
            "xp_total",
            "current_streak",
            "best_streak",
            "last_active_date",
            "bootstrap_version",
            "updated_at",
        ])
        XPEvent.objects.get_or_create(
            user=user,
            source_key=f"bootstrap:v{BOOTSTRAP_VERSION}",
            defaults={
                "kind": XPEvent.KIND_BOOTSTRAP,
                "title": "V50.2 starting progress",
                "amount": bootstrap_xp,
                "metadata": {"version": BOOTSTRAP_VERSION},
            },
        )

    evaluate_achievements(user)
    return _reconcile_streak(profile)


def award_xp(user, *, amount, source_key, title, kind=XPEvent.KIND_ACTIVITY, metadata=None, evaluate=True):
    """Award XP exactly once per user/source_key and return (event, created)."""
    amount = max(0, int(amount or 0))
    ensure_gamification_profile(user)
    with transaction.atomic():
        profile = GamificationProfile.objects.select_for_update().get(user=user)
        try:
            event, created = XPEvent.objects.get_or_create(
                user=user,
                source_key=source_key,
                defaults={
                    "kind": kind,
                    "title": title,
                    "amount": amount,
                    "metadata": metadata or {},
                },
            )
        except IntegrityError:
            event = XPEvent.objects.get(user=user, source_key=source_key)
            created = False
        if created and amount:
            profile.xp_total += amount
            profile.save(update_fields=["xp_total", "updated_at"])
    if created and evaluate:
        evaluate_achievements(user)
    return event, created


def touch_activity(user, *, activity_date=None):
    activity_date = activity_date or timezone.localdate()
    ensure_gamification_profile(user)
    with transaction.atomic():
        profile = GamificationProfile.objects.select_for_update().get(user=user)
        last = profile.last_active_date
        # Historical/replayed activity must never move the streak backwards.
        if last and activity_date < last:
            return profile
        if last == activity_date:
            return profile
        if last == activity_date - timedelta(days=1):
            profile.current_streak += 1
        else:
            profile.current_streak = 1
        profile.best_streak = max(profile.best_streak, profile.current_streak)
        profile.last_active_date = activity_date
        profile.save(update_fields=["current_streak", "best_streak", "last_active_date", "updated_at"])
        return profile


def _increment_quest_metric(user, *, metric, object_key):
    ensure_current_quests(user)
    today = timezone.localdate()
    periods = (
        (QuestProgress.PERIOD_DAILY, today),
        (QuestProgress.PERIOD_WEEKLY, _week_start(today)),
    )
    completed_rows = []

    for period_type, period_start in periods:
        definitions = [item for item in _quest_definitions(period_type, period_start) if item["metric"] == metric]
        for definition in definitions:
            with transaction.atomic():
                row = QuestProgress.objects.select_for_update().get(
                    user=user,
                    code=definition["code"],
                    period_start=period_start,
                )
                if row.completed_at:
                    continue
                seen = list(row.seen_keys or [])
                if object_key in seen:
                    continue
                seen.append(object_key)
                row.seen_keys = seen
                row.progress = min(row.target, row.progress + 1)
                if row.progress >= row.target:
                    row.completed_at = timezone.now()
                row.save(update_fields=["seen_keys", "progress", "completed_at", "updated_at"])
                if row.completed_at:
                    completed_rows.append(row)

    for row in completed_rows:
        _, rewarded = award_xp(
            user,
            amount=row.reward_xp,
            source_key=f"quest:{row.code}:{row.period_start.isoformat()}",
            title=f"Quest complete · {row.title}",
            kind=XPEvent.KIND_QUEST,
            metadata={"quest_code": row.code, "period": row.period_type},
            evaluate=False,
        )
        if rewarded and not row.rewarded_at:
            row.rewarded_at = timezone.now()
            row.save(update_fields=["rewarded_at", "updated_at"])


def record_learning_activity(user, *, activity_key, metrics=(), xp_awards=()):
    """Central V50.2 write path for progression-producing learning actions.

    ``activity_key`` must identify a real user action/object and remain stable on
    retries. ``metrics`` feed current quests. ``xp_awards`` is an iterable of
    dictionaries accepted by award_xp except ``user``. This keeps XP, streaks,
    quests and achievement evaluation synchronized from one call site.
    """
    ensure_gamification_profile(user)
    touch_activity(user)

    for payload in xp_awards:
        award_xp(user, evaluate=False, **payload)

    seen_metrics = set()
    for metric in metrics:
        if metric in seen_metrics:
            continue
        seen_metrics.add(metric)
        _increment_quest_metric(user, metric=metric, object_key=activity_key)

    # Every meaningful learning action also contributes to the generic quest
    # metric, so future SAT/AP integrations only need this one service call.
    _increment_quest_metric(user, metric="learning_action", object_key=activity_key)
    evaluate_achievements(user)


def record_vocabulary_review(user, *, object_key, previous_status, new_status, outcome):
    xp_awards = []
    if previous_status == "new":
        xp_awards.append({
            "amount": 5,
            "source_key": f"vocab:start:{object_key}",
            "title": "Started a vocabulary word",
            "metadata": {"outcome": outcome},
        })
    mastered_now = previous_status != "mastered" and new_status == "mastered"
    if mastered_now:
        xp_awards.append({
            "amount": 10,
            "source_key": f"vocab:mastered:{object_key}",
            "title": "Mastered a vocabulary word",
        })

    metrics = ["vocab_review"]
    if mastered_now:
        metrics.append("vocab_mastered")
    record_learning_activity(
        user,
        activity_key=object_key,
        metrics=metrics,
        xp_awards=xp_awards,
    )


def _achievement_state(user, profile=None):
    profile = profile or GamificationProfile.objects.filter(user=user).first()
    if not profile:
        return {}
    return {
        **level_snapshot(profile.xp_total),
        "best_streak": profile.best_streak,
        "mastered_words": _mastered_word_count(user),
        "completed_quests": _completed_quest_count(user),
    }


def evaluate_achievements(user):
    profile = GamificationProfile.objects.filter(user=user).first()
    if not profile:
        return []
    state = _achievement_state(user, profile)
    unlocked = []
    for definition in ACHIEVEMENTS:
        if not definition["check"](state):
            continue
        achievement, created = UserAchievement.objects.get_or_create(
            user=user,
            code=definition["code"],
            defaults={
                "title": definition["title"],
                "description": definition["description"],
                "icon": definition["icon"],
            },
        )
        if created:
            unlocked.append(achievement)
    return unlocked


def gamification_shell_context(user):
    profile = ensure_gamification_profile(user)
    snapshot = level_snapshot(profile.xp_total)
    return {
        "gamification": {
            **snapshot,
            "current_streak": profile.current_streak,
            "best_streak": profile.best_streak,
        }
    }


def gamification_context(user):
    profile = ensure_gamification_profile(user)
    # Catch achievements that became eligible through imported/historical data.
    evaluate_achievements(user)
    snapshot = level_snapshot(profile.xp_total)
    daily, weekly = ensure_current_quests(user)
    unlocked_rows = {row.code: row for row in UserAchievement.objects.filter(user=user)}
    state = _achievement_state(user, profile)
    achievement_catalog = []
    for definition in ACHIEVEMENTS:
        current = int(state.get(definition["progress_key"], 0) or 0)
        target = int(definition["target"])
        achievement_catalog.append({
            "code": definition["code"],
            "title": definition["title"],
            "description": definition["description"],
            "icon": definition["icon"],
            "unlocked": definition["code"] in unlocked_rows,
            "unlocked_at": getattr(unlocked_rows.get(definition["code"]), "unlocked_at", None),
            "progress": min(target, current),
            "target": target,
            "percent": min(100, round((min(target, current) / max(1, target)) * 100)),
        })
    achievements = list(unlocked_rows.values())[:6]
    recent_events = list(XPEvent.objects.filter(user=user, amount__gt=0)[:6])
    daily_reward = sum(row.reward_xp for row in daily)
    weekly_reward = sum(row.reward_xp for row in weekly)
    return {
        "gamification": {
            **snapshot,
            "current_streak": profile.current_streak,
            "best_streak": profile.best_streak,
            "daily_quests": daily,
            "weekly_quests": weekly,
            "daily_completed": sum(1 for row in daily if row.completed_at),
            "daily_total": len(daily),
            "daily_reward": daily_reward,
            "weekly_completed": sum(1 for row in weekly if row.completed_at),
            "weekly_total": len(weekly),
            "weekly_reward": weekly_reward,
            "achievements": achievements,
            "achievement_catalog": achievement_catalog,
            "achievement_count": len(unlocked_rows),
            "achievement_total": len(achievement_catalog),
            "quest_catalog_size": len(DAILY_QUESTS) + len(WEEKLY_QUESTS),
            "recent_events": recent_events,
        }
    }

"""V50.5 Mako — MakonBook's study companion.

Mako is deliberately rule-based: every line it says is derived from data the
student can already see (XP events, quests, streak, homework deadlines, weak
topics from scored attempts, vocabulary progress, goal setup). It never claims
to be an AI, never invents scores or predictions, and never writes anything.

``mako_state`` is a pure function over the Home context that the dashboard
view has already computed, so rendering Mako adds no database queries.
"""
from __future__ import annotations

from datetime import timedelta

from django.urls import NoReverseMatch, reverse
from django.utils import timezone

STATE_CELEBRATE = "celebrate"
STATE_NUDGE = "nudge"
STATE_FOCUS = "focus"
STATE_WELCOME = "welcome"
STATE_IDLE = "idle"
STATES = (STATE_CELEBRATE, STATE_NUDGE, STATE_FOCUS, STATE_WELCOME, STATE_IDLE)

# A weak topic needs enough answers to be a signal rather than noise.
WEAK_TOPIC_MIN_ANSWERS = 3
WEAK_TOPIC_MAX_ACCURACY = 70
DUE_SOON_HOURS = 24
MAX_RECOMMENDATIONS = 3


def _url(name, *args):
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return ""


def _local_date(value):
    if value is None:
        return None
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.date()


def _xp_today(gamification, today):
    events = gamification.get("recent_events") or []
    return sum(
        int(getattr(event, "amount", 0) or 0)
        for event in events
        if _local_date(getattr(event, "created_at", None)) == today
    )


def _section_label(section):
    return "Math" if str(section).lower() == "math" else "Reading & Writing"


def mako_state(
    *,
    gamification=None,
    due_items=None,
    weak_topics=None,
    vocabulary=None,
    goal=None,
    has_classroom=False,
    now=None,
):
    """Return Mako's mood, what it says, and up to three next steps."""
    now = now or timezone.now()
    today = timezone.localdate(now)
    gamification = gamification or {}
    due_items = list(due_items or [])
    weak_topics = list(weak_topics or [])
    vocabulary = vocabulary or {}

    level = int(gamification.get("level") or 1)
    xp_total = int(gamification.get("xp_total") or 0)
    level_floor = int(gamification.get("level_floor_xp") or 0)
    streak = int(gamification.get("current_streak") or 0)
    daily_total = int(gamification.get("daily_total") or 0)
    daily_done = int(gamification.get("daily_completed") or 0)
    xp_today = _xp_today(gamification, today)
    active_today = xp_today > 0

    leveled_up_today = level > 1 and xp_today > 0 and (xp_total - xp_today) < level_floor
    quests_done_today = daily_total > 0 and daily_done >= daily_total

    due_soon = None
    for item in due_items:
        due_at = item.get("due_at")
        if due_at and now <= due_at <= now + timedelta(hours=DUE_SOON_HOURS):
            due_soon = item
            break

    weakest = next(
        (
            row for row in weak_topics
            if int(row.get("total") or 0) >= WEAK_TOPIC_MIN_ANSWERS
            and int(row.get("accuracy") or 0) <= WEAK_TOPIC_MAX_ACCURACY
        ),
        None,
    )

    learning_words = int(vocabulary.get("learning_words") or 0)
    unseen_words = int(vocabulary.get("unseen_words") or 0)
    goal_configured = bool(getattr(goal, "is_configured", True)) if goal is not None else True

    # ---- next steps (ordered by urgency, deduplicated by URL) ----
    recommendations = []

    def add(kind, title, reason, url, icon):
        if not url or any(rec["url"] == url for rec in recommendations):
            return
        recommendations.append({"kind": kind, "title": title, "reason": reason, "url": url, "icon": icon})

    if due_soon:
        add("deadline", due_soon.get("title") or "Homework", "Due within 24 hours.", due_soon.get("url"), "bi-alarm")
    elif due_items:
        first = due_items[0]
        add("deadline", first.get("title") or "Homework", f"Next deadline · {first.get('meta', '')}".strip(" ·"), first.get("url"), first.get("icon") or "bi-clipboard-check")
    if weakest:
        add(
            "weak_topic",
            f"Practise {weakest['name']}",
            f"{weakest['accuracy']}% correct over {weakest['total']} {_section_label(weakest.get('section'))} answers.",
            _url("student_practice_root"),
            "bi-bullseye",
        )
    if learning_words:
        add("vocabulary", "Review vocabulary", f"{learning_words} word{'s' if learning_words != 1 else ''} still in learning.", _url("vocabulary_root"), "bi-translate")
    elif unseen_words and not active_today:
        add("vocabulary", "Learn new words", f"{unseen_words} words you have not opened yet.", _url("vocabulary_root"), "bi-translate")
    if not goal_configured:
        add("goal", "Set your SAT goal", "A target score and date let MakonBook plan your weeks.", _url("student_dashboard_root") + "?goal=1", "bi-flag")
    if not has_classroom:
        add("classroom", "Join a classroom", "Your teacher's tests and homework unlock after approval.", _url("events"), "bi-people")
    if daily_total and not quests_done_today:
        add("quests", "Finish today's quests", f"{daily_done}/{daily_total} done today.", _url("vocabulary_root"), "bi-check2-square")
    recommendations = recommendations[:MAX_RECOMMENDATIONS]

    # ---- mood + line (most meaningful event wins) ----
    if leveled_up_today:
        state, event = STATE_CELEBRATE, f"level-{level}"
        headline = f"Level {level} unlocked!"
        message = f"You reached {gamification.get('level_title') or f'Level {level}'} today. Keep the momentum going."
    elif due_soon:
        state, event = STATE_NUDGE, f"due-{today.isoformat()}"
        headline = "A deadline is close"
        message = f"“{due_soon.get('title')}” is due within 24 hours. Let's get it done first."
    elif quests_done_today:
        state, event = STATE_CELEBRATE, f"quests-{today.isoformat()}"
        headline = "All daily quests done!"
        message = "Every quest for today is complete. Anything extra is a bonus."
    elif streak >= 2 and not active_today:
        state, event = STATE_NUDGE, f"streak-{today.isoformat()}"
        headline = f"Keep your {streak}-day streak"
        message = "One short session today keeps your streak alive."
    elif weakest:
        state, event = STATE_FOCUS, f"weak-{today.isoformat()}"
        headline = f"Let's fix {weakest['name']}"
        message = f"It is your lowest topic right now at {weakest['accuracy']}% correct. A focused round helps most."
    elif not has_classroom or not goal_configured:
        state, event = STATE_WELCOME, "welcome"
        headline = "Hi, I'm Mako!"
        message = "I'll point you to the most useful next step as you study."
    else:
        state, event = STATE_IDLE, f"idle-{today.isoformat()}"
        headline = "Nice and steady"
        message = (
            f"You earned {xp_today} XP today." if active_today
            else "Pick any next step below to start today's session."
        )

    return {
        "state": state,
        "event": event,
        "headline": headline,
        "message": message,
        "recommendations": recommendations,
        "streak": streak,
        "level": level,
    }

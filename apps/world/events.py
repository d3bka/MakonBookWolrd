"""V50.7 World Events: cooperative goals and seasonal competitions.

Standings are computed from completed 1v1 matches whose ``completed_at`` falls
inside the event window. To keep events fair, at most ``PAIR_DAILY_CAP``
matches between the same two players count per day (so two friends cannot
farm an event by playing each other all night). Rewards are XP only, paid once
per player per event through the idempotent XP ledger.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.base.seasons import SEASONS, season_for_date
from apps.gamification.services import award_xp

from .models import WorldEvent, WorldMatch

PAIR_DAILY_CAP = 3
CACHE_SECONDS = 60
LEADERBOARD_SIZE = 10


def _counted_matches(event):
    rows = WorldMatch.objects.filter(
        status=WorldMatch.STATUS_COMPLETED,
        completed_at__gte=event.starts_at, completed_at__lt=event.ends_at,
        player2__isnull=False,
    )
    if event.subject:
        rows = rows.filter(subject=event.subject)
    per_pair_day = Counter()
    for row in rows.order_by("completed_at").values(
        "player1_id", "player2_id", "winner_id", "player1_score", "player2_score", "completed_at",
    ):
        key = (min(row["player1_id"], row["player2_id"]), max(row["player1_id"], row["player2_id"]),
               timezone.localdate(row["completed_at"]))
        per_pair_day[key] += 1
        if per_pair_day[key] <= PAIR_DAILY_CAP:
            yield row


def standings(event):
    """user_id -> metric value, cached briefly (events page is read-heavy)."""
    cache_key = f"world-event:{event.pk}:{event.ends_at.timestamp()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    totals = defaultdict(int)
    for row in _counted_matches(event):
        for uid, score in ((row["player1_id"], row["player1_score"]), (row["player2_id"], row["player2_score"])):
            if event.metric == WorldEvent.METRIC_WINS:
                totals[uid] += int(row["winner_id"] == uid)
            elif event.metric == WorldEvent.METRIC_MATCHES:
                totals[uid] += 1
            else:
                totals[uid] += int(score or 0)
    result = {uid: value for uid, value in totals.items() if value > 0}
    cache.set(cache_key, result, CACHE_SECONDS)
    return result


def ranked(totals):
    return sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))


def phase(event, now=None):
    now = now or timezone.now()
    if now < event.starts_at:
        return "upcoming"
    if now >= event.ends_at:
        return "ended"
    return "live"


def settle(event, now=None):
    """Pay rewards once an event has ended. Safe to call repeatedly."""
    now = now or timezone.now()
    if event.settled_at or now < event.ends_at:
        return 0
    with transaction.atomic():
        locked = WorldEvent.objects.select_for_update().get(pk=event.pk)
        if locked.settled_at:
            return 0
        cache.delete(f"world-event:{locked.pk}:{locked.ends_at.timestamp()}")
        totals = standings(locked)
        if locked.kind == WorldEvent.KIND_COOP:
            winners = list(totals) if locked.goal and sum(totals.values()) >= locked.goal else []
        else:
            winners = [uid for uid, _ in ranked(totals)[: locked.top_rewarded]]
        users = User.objects.in_bulk(winners)
        for uid in winners:
            if uid in users and locked.reward_xp:
                award_xp(users[uid], amount=locked.reward_xp, source_key=f"world-event:{locked.pk}:{uid}",
                         title=f"World event: {locked.title}", metadata={"event_id": locked.pk})
        locked.settled_at = now
        locked.save(update_fields=["settled_at"])
        event.settled_at = now
        return len(winners)


def _card(event, user, now):
    totals = standings(event)
    order = ranked(totals)
    rank = next((i + 1 for i, (uid, _) in enumerate(order) if uid == user.pk), None)
    names = User.objects.in_bulk([uid for uid, _ in order[:LEADERBOARD_SIZE]])
    leaderboard = [{
        "rank": i + 1, "value": value, "is_me": uid == user.pk,
        "name": (names[uid].get_full_name().strip() or names[uid].username) if uid in names else "Player",
    } for i, (uid, value) in enumerate(order[:LEADERBOARD_SIZE])]
    total = sum(totals.values())
    return {
        "event": event,
        "phase": phase(event, now),
        "my_value": totals.get(user.pk, 0),
        "my_rank": rank,
        "players": len(totals),
        "total": total,
        "percent": min(100, round(total / event.goal * 100)) if event.kind == WorldEvent.KIND_COOP and event.goal else None,
        "goal_reached": event.kind == WorldEvent.KIND_COOP and event.goal and total >= event.goal,
        "leaderboard": leaderboard,
        "in_reward_zone": bool(rank and event.kind == WorldEvent.KIND_COMPETITION and rank <= event.top_rewarded),
    }


def events_for(user, now=None):
    now = now or timezone.now()
    events = list(WorldEvent.objects.filter(is_published=True, ends_at__gte=now - timedelta(days=30)).order_by("starts_at"))
    for event in events:
        if phase(event, now) == "ended" and not event.settled_at:
            settle(event, now)
    cards = [_card(e, user, now) for e in events]
    return {
        "live": [c for c in cards if c["phase"] == "live"],
        "upcoming": [c for c in cards if c["phase"] == "upcoming"],
        "ended": sorted((c for c in cards if c["phase"] == "ended"), key=lambda c: c["event"].ends_at, reverse=True),
    }


SEASON_CUPS = {"winter": "Qish Cup", "spring": "Navro'z Cup", "summer": "Yoz Cup", "autumn": "Kuz Cup"}
SEASON_MONTHS = {"winter": (12, 3), "spring": (3, 6), "summer": (6, 9), "autumn": (9, 12)}


def season_window(day):
    """Start/end (aware datetimes) of the calendar season containing ``day``."""
    key = season_for_date(day)
    start_month, end_month = SEASON_MONTHS[key]
    start_year = day.year - 1 if key == "winter" and day.month < 3 else day.year
    end_year = start_year + 1 if key == "winter" else start_year
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime(start_year, start_month, 1), tz)
    end = timezone.make_aware(datetime(end_year, end_month, 1), tz)
    return key, start, end


def ensure_seasonal_competition(day=None):
    """Create this season's cup (a wins competition) if staff haven't already."""
    day = day or timezone.localdate()
    key, start, end = season_window(day)
    existing = WorldEvent.objects.filter(kind=WorldEvent.KIND_COMPETITION, season=key, starts_at=start).first()
    if existing:
        return existing, False
    return WorldEvent.objects.create(
        title=f"{SEASON_CUPS[key]} {start.year}" + (f"/{str(end.year)[2:]}" if end.year != start.year else ""),
        description=f"Seasonal competition — most World wins this {SEASONS[key]['label'].lower()} ({SEASONS[key]['uz']}). Top 10 earn bonus XP.",
        kind=WorldEvent.KIND_COMPETITION, metric=WorldEvent.METRIC_WINS, season=key,
        starts_at=start, ends_at=end, top_rewarded=10, reward_xp=150,
    ), True


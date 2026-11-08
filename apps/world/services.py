from __future__ import annotations

import math
import random
import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.gamification.services import award_xp
from apps.sat.models import English_Question, Math_Question
from apps.sat.rich_text import question_display

from .models import (
    GameQuestionPool,
    WorldAnswer,
    WorldMatch,
    WorldQuestionTicket,
    WorldRating,
    WorldMultiplayerRoom,
    WorldMultiplayerSeat,
    WorldMultiplayerQuestionTicket,
    WorldMultiplayerAnswer,
    WorldMultiplayerSeatSwapRequest,
)


QUESTION_COUNT = 5
QUESTION_TIME_LIMIT_SECONDS = 75
HEARTBEAT_STALE_SECONDS = 45
HEARTBEAT_GRACE_SECONDS = 25
RECENT_QUESTION_DAYS = 30
RECENT_PAIR_HOURS = 24
QUEUE_MAX_SECONDS = 60
MATCH_INTRO_SECONDS = 5

DIFFICULTY_POINTS = {
    GameQuestionPool.DIFFICULTY_EASY: 80,
    GameQuestionPool.DIFFICULTY_MEDIUM: 120,
    GameQuestionPool.DIFFICULTY_HARD: 180,
}


def ensure_ratings(user):
    ratings = {}
    for subject in (WorldRating.SUBJECT_MATH, WorldRating.SUBJECT_RW):
        ratings[subject], _ = WorldRating.objects.get_or_create(user=user, subject=subject)
    return ratings


def rating_rank(rating: WorldRating) -> int:
    return WorldRating.objects.filter(subject=rating.subject, rating__gt=rating.rating).count() + 1


def leaderboard(subject: str, limit: int = 50):
    return list(
        WorldRating.objects.filter(subject=subject)
        .select_related("user")
        .order_by("-rating", "user_id")[:limit]
    )


def normalize_choice(value: str) -> str:
    raw = (value or "").strip()
    if raw.upper() in {"A", "B", "C", "D"}:
        return raw.upper()
    return raw.casefold()


def answer_is_correct(question, selected: str) -> bool:
    expected = normalize_choice(question.answer or "")
    candidate = normalize_choice(selected)
    if expected in {"A", "B", "C", "D"}:
        return candidate == expected
    choices = {
        "A": normalize_choice(question.a or ""),
        "B": normalize_choice(question.b or ""),
        "C": normalize_choice(question.c or ""),
        "D": normalize_choice(question.d or ""),
    }
    selected_letter = candidate.upper() if candidate.upper() in choices else None
    if selected_letter and choices[selected_letter]:
        return choices[selected_letter] == expected
    return candidate == expected


def _structurally_valid_question(question, subject: str) -> bool:
    if not question or not (question.question or "").strip() or not (question.answer or "").strip():
        return False
    if subject == WorldRating.SUBJECT_MATH and getattr(question, "written", False):
        return False
    if subject == WorldRating.SUBJECT_RW and getattr(question, "response_type", "multiple_choice") != "multiple_choice":
        return False
    choices = [getattr(question, key, None) for key in ("a", "b", "c", "d")]
    if any(not (choice or "").strip() for choice in choices):
        return False
    expected = normalize_choice(question.answer or "")
    if expected in {"A", "B", "C", "D"}:
        return True
    return expected in {normalize_choice(choice) for choice in choices}


def _infer_difficulty(question) -> str:
    source = str(getattr(question, "source_difficulty", "") or "").lower()
    if source in {GameQuestionPool.DIFFICULTY_EASY, GameQuestionPool.DIFFICULTY_MEDIUM, GameQuestionPool.DIFFICULTY_HARD}:
        # Synced from makonbook-api, which tags each question.
        return source
    # The source bank does not yet expose a universal calibrated difficulty field.
    # Module 2 is adaptive/harder on average; late questions are also a useful
    # conservative heuristic until the quality team calibrates rows explicitly.
    module = str(getattr(question, "module", "") or "").lower()
    number = int(getattr(question, "number", 0) or 0)
    if "2" in module and number >= 15:
        return GameQuestionPool.DIFFICULTY_HARD
    if "2" in module or number >= 10:
        return GameQuestionPool.DIFFICULTY_MEDIUM
    return GameQuestionPool.DIFFICULTY_EASY


def sync_question_pool(*, subject: str | None = None, limit: int | None = None) -> dict:
    subjects = [subject] if subject else [WorldRating.SUBJECT_MATH, WorldRating.SUBJECT_RW]
    summary = {"created": 0, "updated": 0, "disabled": 0}
    for current in subjects:
        if current not in {WorldRating.SUBJECT_MATH, WorldRating.SUBJECT_RW}:
            raise ValueError("Invalid subject")
        model = Math_Question if current == WorldRating.SUBJECT_MATH else English_Question
        qs = model.objects.all().order_by("-id")
        if limit:
            qs = qs[: int(limit)]
        for question in qs.iterator() if hasattr(qs, "iterator") else qs:
            valid = _structurally_valid_question(question, current)
            lookup = {"math_question": question} if current == WorldRating.SUBJECT_MATH else {"english_question": question}
            defaults = {
                "subject": current,
                "difficulty": _infer_difficulty(question),
                "game_enabled": valid,
                "quality_verified": valid,
                "estimated_seconds": QUESTION_TIME_LIMIT_SECONDS,
            }
            row, created = GameQuestionPool.objects.get_or_create(**lookup, defaults=defaults)
            if created:
                summary["created"] += 1
                continue
            changed = False
            for field, value in defaults.items():
                if field in {"difficulty"} and row.quality_verified:
                    # Preserve manual calibration from admin once a row is verified.
                    continue
                if getattr(row, field) != value:
                    setattr(row, field, value)
                    changed = True
            if changed:
                row.save(update_fields=["subject", "difficulty", "game_enabled", "quality_verified", "estimated_seconds", "updated_at"])
                summary["updated"] += 1
            if not valid:
                summary["disabled"] += 1
    return summary


def ensure_question_pool(subject: str, minimum: int = QUESTION_COUNT) -> None:
    available = GameQuestionPool.objects.filter(subject=subject, game_enabled=True, quality_verified=True).count()
    if available >= minimum:
        return
    sync_question_pool(subject=subject, limit=1000)


def _recent_pool_ids_for_users(users) -> set[int]:
    user_ids = [user.id for user in users if user]
    if not user_ids:
        return set()
    cutoff = timezone.now() - timedelta(days=RECENT_QUESTION_DAYS)
    return set(
        WorldAnswer.objects.filter(user_id__in=user_ids, answered_at__gte=cutoff, pool_entry_id__isnull=False)
        .values_list("pool_entry_id", flat=True)
    )


def pick_question_pool(subject: str, players, count: int = QUESTION_COUNT) -> list[GameQuestionPool]:
    ensure_question_pool(subject, count)
    recent = _recent_pool_ids_for_users(players)
    qs = list(
        GameQuestionPool.objects.filter(subject=subject, game_enabled=True, quality_verified=True)
        .exclude(pk__in=recent)
        .select_related("math_question", "english_question")
        .order_by("times_used", "last_used_at", "id")[: max(count * 8, 40)]
    )
    if len(qs) < count:
        qs = list(
            GameQuestionPool.objects.filter(subject=subject, game_enabled=True, quality_verified=True)
            .select_related("math_question", "english_question")
            .order_by("times_used", "last_used_at", "id")[: max(count * 8, 40)]
        )
    if len(qs) < count:
        return []

    # Keep the match varied without sacrificing low-use prioritization.
    bands = {
        GameQuestionPool.DIFFICULTY_EASY: [row for row in qs if row.difficulty == GameQuestionPool.DIFFICULTY_EASY],
        GameQuestionPool.DIFFICULTY_MEDIUM: [row for row in qs if row.difficulty == GameQuestionPool.DIFFICULTY_MEDIUM],
        GameQuestionPool.DIFFICULTY_HARD: [row for row in qs if row.difficulty == GameQuestionPool.DIFFICULTY_HARD],
    }
    desired = [GameQuestionPool.DIFFICULTY_EASY, GameQuestionPool.DIFFICULTY_MEDIUM, GameQuestionPool.DIFFICULTY_MEDIUM, GameQuestionPool.DIFFICULTY_HARD, GameQuestionPool.DIFFICULTY_HARD]
    selected = []
    used = set()
    for difficulty in desired[:count]:
        candidates = [row for row in bands[difficulty] if row.id not in used]
        if candidates:
            row = random.choice(candidates[: min(8, len(candidates))])
            selected.append(row)
            used.add(row.id)
    for row in qs:
        if len(selected) >= count:
            break
        if row.id not in used:
            selected.append(row)
            used.add(row.id)
    return selected[:count]


def _rating_for(user, subject):
    rating, _ = WorldRating.objects.get_or_create(user=user, subject=subject)
    return rating


def _queue_rating_window(wait_seconds: float) -> int:
    # Ranked search gets progressively broader, but never waits forever.
    # The final 15 seconds allow a wider fair-match window before the hard 60s timeout.
    if wait_seconds >= 45:
        return 500
    if wait_seconds >= 30:
        return 300
    if wait_seconds >= 15:
        return 175
    return 100




def expire_waiting_match(match: WorldMatch, *, now=None) -> bool:
    """Cancel a stale matchmaking row once the hard queue limit is reached."""
    if not match or match.status != WorldMatch.STATUS_WAITING:
        return False
    now = now or timezone.now()
    if (now - match.created_at).total_seconds() < QUEUE_MAX_SECONDS:
        return False
    updated = WorldMatch.objects.filter(pk=match.pk, status=WorldMatch.STATUS_WAITING).update(
        status=WorldMatch.STATUS_CANCELLED
    )
    if updated:
        match.status = WorldMatch.STATUS_CANCELLED
        return True
    return False


def queue_seconds_remaining(match: WorldMatch, *, now=None) -> int:
    if not match or match.status != WorldMatch.STATUS_WAITING:
        return 0
    now = now or timezone.now()
    elapsed = max(0, int((now - match.created_at).total_seconds()))
    return max(0, QUEUE_MAX_SECONDS - elapsed)

def _recent_pair_count(user_a, user_b) -> int:
    cutoff = timezone.now() - timedelta(hours=RECENT_PAIR_HOURS)
    return WorldMatch.objects.filter(
        status=WorldMatch.STATUS_COMPLETED,
        mode=WorldMatch.MODE_RANKED,
        completed_at__gte=cutoff,
    ).filter(
        Q(player1=user_a, player2=user_b) | Q(player1=user_b, player2=user_a)
    ).count()


def _mmr_weight_for_pair(user_a, user_b) -> Decimal:
    repeats = _recent_pair_count(user_a, user_b)
    if repeats <= 0:
        return Decimal("1.00")
    if repeats == 1:
        return Decimal("0.60")
    if repeats == 2:
        return Decimal("0.30")
    return Decimal("0.10")


def _waiting_opponents(*, user, subject: str, mode: str, now, exclude_match_ids=None, limit: int = 40):
    exclude_ids = [pk for pk in (exclude_match_ids or []) if pk]
    waiting = list(
        WorldMatch.objects.select_for_update()
        .filter(status=WorldMatch.STATUS_WAITING, subject=subject, mode=mode, player2__isnull=True, invitee__isnull=True)
        .exclude(player1=user)
        .order_by("created_at")[: max(1, limit)]
    )
    if exclude_ids:
        waiting = [candidate for candidate in waiting if candidate.pk not in exclude_ids]
    active = []
    for candidate in waiting:
        wait_seconds = max(0.0, (now - candidate.created_at).total_seconds())
        if wait_seconds >= QUEUE_MAX_SECONDS:
            expire_waiting_match(candidate, now=now)
            continue
        active.append(candidate)
    return active


def _best_waiting_opponent(*, user, subject: str, mode: str, my_created_at, now, exclude_match_ids=None):
    my_rating = _rating_for(user, subject)
    opponent_match = None
    best_delta = None
    my_wait_seconds = max(0.0, (now - my_created_at).total_seconds()) if my_created_at else 0.0
    for candidate in _waiting_opponents(
        user=user,
        subject=subject,
        mode=mode,
        now=now,
        exclude_match_ids=exclude_match_ids,
    ):
        candidate_rating = _rating_for(candidate.player1, subject)
        rating_delta = abs(candidate_rating.rating - my_rating.rating)
        effective_wait = max(my_wait_seconds, max(0.0, (now - candidate.created_at).total_seconds()))
        if mode == WorldMatch.MODE_RANKED and rating_delta > _queue_rating_window(effective_wait):
            continue
        if best_delta is None or rating_delta < best_delta or (rating_delta == best_delta and candidate.created_at < opponent_match.created_at):
            opponent_match = candidate
            best_delta = rating_delta
    return opponent_match


def _activate_waiting_match(match: WorldMatch, *, opponent_user, now):
    if match.status != WorldMatch.STATUS_WAITING or match.player2_id:
        return match
    subject = match.subject
    pool_rows = pick_question_pool(subject, [match.player1, opponent_user], QUESTION_COUNT)
    if len(pool_rows) < QUESTION_COUNT:
        raise RuntimeError("Not enough verified World questions for this subject yet.")
    p1_rating = _rating_for(match.player1, subject)
    p2_rating = _rating_for(opponent_user, subject)
    match.player2 = opponent_user
    match.status = WorldMatch.STATUS_ACTIVE
    match.started_at = now
    match.player1_last_seen_at = now
    match.player2_last_seen_at = now
    match.question_pool_ids = [row.id for row in pool_rows]
    match.question_ids = [
        row.math_question_id if subject == WorldRating.SUBJECT_MATH else row.english_question_id
        for row in pool_rows
    ]
    match.player1_rating_before = p1_rating.rating
    match.player2_rating_before = p2_rating.rating
    match.player1_rating_after = p1_rating.rating
    match.player2_rating_after = p2_rating.rating
    match.mmr_weight = _mmr_weight_for_pair(match.player1, opponent_user) if match.mode == WorldMatch.MODE_RANKED else Decimal("1.00")
    match.save(update_fields=[
        "player2", "status", "started_at", "player1_last_seen_at", "player2_last_seen_at",
        "question_pool_ids", "question_ids", "player1_rating_before", "player2_rating_before",
        "player1_rating_after", "player2_rating_after", "mmr_weight",
    ])
    GameQuestionPool.objects.filter(pk__in=match.question_pool_ids).update(
        times_used=F("times_used") + 1,
        last_used_at=now,
    )
    return match


def reconcile_waiting_match(match: WorldMatch, *, now=None):
    if not match or match.status != WorldMatch.STATUS_WAITING:
        return match, False
    now = now or timezone.now()
    with transaction.atomic():
        locked = WorldMatch.objects.select_for_update().get(pk=match.pk)
        if locked.status != WorldMatch.STATUS_WAITING:
            return locked, False
        if expire_waiting_match(locked, now=now):
            return locked, False
        # Private rematch invites are accepted only by their explicit invitee.
        # Never let ordinary queue reconciliation steal the room.
        if locked.invitee_id:
            return locked, False

        opponent_match = _best_waiting_opponent(
            user=locked.player1,
            subject=locked.subject,
            mode=locked.mode,
            my_created_at=locked.created_at,
            now=now,
            exclude_match_ids=[locked.pk],
        )
        if not opponent_match:
            return locked, False

        # Prefer the older queue row as the canonical match room to avoid fair-order weirdness.
        primary = locked
        secondary = WorldMatch.objects.select_for_update().get(pk=opponent_match.pk)
        if secondary.created_at < primary.created_at:
            primary, secondary = secondary, primary

        if primary.status != WorldMatch.STATUS_WAITING or primary.player2_id:
            return locked, False
        if secondary.status != WorldMatch.STATUS_WAITING or secondary.player2_id:
            return locked, False

        active_match = _activate_waiting_match(primary, opponent_user=secondary.player1, now=now)
        WorldMatch.objects.filter(pk=secondary.pk, status=WorldMatch.STATUS_WAITING).update(status=WorldMatch.STATUS_CANCELLED)
        secondary.status = WorldMatch.STATUS_CANCELLED
        return active_match, True


def active_match_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return (
        WorldMatch.objects.filter(status=WorldMatch.STATUS_ACTIVE)
        .filter(Q(player1=user) | Q(player2=user))
        .order_by("-created_at")
        .first()
    )


def join_queue(user, *, subject: str, mode: str):
    if subject not in {WorldRating.SUBJECT_MATH, WorldRating.SUBJECT_RW}:
        raise ValueError("Invalid subject")
    if mode not in {WorldMatch.MODE_QUICK, WorldMatch.MODE_RANKED}:
        raise ValueError("Invalid match mode")

    ensure_ratings(user)
    now = timezone.now()
    with transaction.atomic():
        existing = (
            WorldMatch.objects.select_for_update()
            .filter(status__in=[WorldMatch.STATUS_WAITING, WorldMatch.STATUS_ACTIVE])
            .filter(Q(player1=user) | Q(player2=user))
            .filter(Q(status=WorldMatch.STATUS_ACTIVE) | Q(invitee__isnull=True))
            .order_by("-created_at")
            .first()
        )
        if existing:
            if existing.status == WorldMatch.STATUS_WAITING:
                if expire_waiting_match(existing, now=now):
                    existing = None
                else:
                    if existing.subject == subject and existing.mode == mode:
                        reconciled, matched = reconcile_waiting_match(existing, now=now)
                        return reconciled, matched
                    return existing, False
            else:
                return existing, False

        opponent_match = _best_waiting_opponent(
            user=user,
            subject=subject,
            mode=mode,
            my_created_at=now,
            now=now,
        )
        if opponent_match:
            locked_opponent = WorldMatch.objects.select_for_update().get(pk=opponent_match.pk)
            if locked_opponent.status == WorldMatch.STATUS_WAITING and not locked_opponent.player2_id:
                activated = _activate_waiting_match(locked_opponent, opponent_user=user, now=now)
                return activated, True

        mine = WorldMatch.objects.create(subject=subject, mode=mode, player1=user, status=WorldMatch.STATUS_WAITING)
        return mine, True


def create_rematch_invite(match: WorldMatch, requester):
    """Create a private rematch challenge.

    Chess-style behavior:
    - only one live challenge may exist for the completed source match/pair;
    - clicking Rematch twice is idempotent;
    - if both players request a rematch at nearly the same time, the second
      request accepts the first instead of creating crossed waiting rows.
    """
    if not match or match.status != WorldMatch.STATUS_COMPLETED or not match.includes(requester):
        raise ValueError("Rematch is only available after a completed match.")
    opponent = match.opponent_for(requester)
    if not opponent:
        raise ValueError("Opponent unavailable.")
    if active_match_for_user(requester) or active_match_for_user(opponent):
        raise ValueError("One of the players is already in an active match.")
    now = timezone.now()
    with transaction.atomic():
        pair_rows = list(
            WorldMatch.objects.select_for_update()
            .filter(status=WorldMatch.STATUS_WAITING, rematch_of=match)
            .filter(
                Q(player1=requester, invitee=opponent)
                | Q(player1=opponent, invitee=requester)
            )
            .order_by("created_at")
        )
        for row in pair_rows:
            if queue_seconds_remaining(row, now=now) <= 0:
                row.status = WorldMatch.STATUS_CANCELLED
                row.save(update_fields=["status"])
                continue
            if row.player1_id == requester.id:
                return row, False
            # Reciprocal request: the other player already challenged us.
            # Accept it immediately, exactly like two players both clicking
            # rematch after the same game.
            active = _activate_waiting_match(row, opponent_user=requester, now=now)
            return active, False

        invite = WorldMatch.objects.create(
            subject=match.subject,
            mode=match.mode,
            player1=requester,
            invitee=opponent,
            rematch_of=match,
            status=WorldMatch.STATUS_WAITING,
        )
        return invite, True


def incoming_rematch_invite(user):
    """Return the newest usable rematch challenge for ``user``."""
    if not user or not getattr(user, "is_authenticated", False):
        return None
    now = timezone.now()
    rows = list(
        WorldMatch.objects.filter(status=WorldMatch.STATUS_WAITING, invitee=user, player2__isnull=True)
        .select_related("player1", "rematch_of")
        .order_by("-created_at")[:5]
    )
    for invite in rows:
        if queue_seconds_remaining(invite, now=now) <= 0:
            expire_waiting_match(invite, now=now)
            continue
        return invite
    return None


def accept_rematch_invite(match: WorldMatch, user):
    if not match or match.status != WorldMatch.STATUS_WAITING or match.player2_id:
        raise ValueError("This rematch invite is no longer available.")
    if match.invitee_id != user.id:
        raise ValueError("This rematch invite is not for this account.")
    if queue_seconds_remaining(match) <= 0:
        expire_waiting_match(match)
        raise ValueError("This rematch invite expired.")
    if active_match_for_user(match.player1) or active_match_for_user(user):
        raise ValueError("One of the players is already in an active match.")
    with transaction.atomic():
        locked = WorldMatch.objects.select_for_update().get(pk=match.pk)
        if locked.status != WorldMatch.STATUS_WAITING or locked.invitee_id != user.id or locked.player2_id:
            raise ValueError("This rematch invite is no longer available.")
        return _activate_waiting_match(locked, opponent_user=user, now=timezone.now())


def decline_rematch_invite(match: WorldMatch, user):
    if not match or match.status != WorldMatch.STATUS_WAITING or match.invitee_id != user.id:
        return False
    match.status = WorldMatch.STATUS_CANCELLED
    match.save(update_fields=["status"])
    return True


def cancel_waiting_match(match: WorldMatch, user):
    if match.player1_id != user.id or match.status != WorldMatch.STATUS_WAITING:
        return False
    match.status = WorldMatch.STATUS_CANCELLED
    match.save(update_fields=["status"])
    return True


def get_pool_entry(match: WorldMatch, index: int):
    if index < 0 or index >= match.total_questions:
        return None
    if match.question_pool_ids:
        try:
            pool_id = match.question_pool_ids[index]
        except (IndexError, TypeError):
            return None
        return GameQuestionPool.objects.select_related("math_question", "english_question").filter(pk=pool_id).first()
    return None


def get_question(match: WorldMatch, index: int):
    pool = get_pool_entry(match, index)
    if pool:
        return pool.question
    if index < 0 or index >= len(match.question_ids or []):
        return None
    question_id = match.question_ids[index]
    model = Math_Question if match.subject == WorldRating.SUBJECT_MATH else English_Question
    return model.objects.filter(pk=question_id).first()


def answered_counts(match: WorldMatch) -> tuple[int, int]:
    counts = {
        row["user"]: row["count"]
        for row in WorldAnswer.objects.filter(match=match)
        .values("user")
        .annotate(count=Count("id"))
    }
    return counts.get(match.player1_id, 0), counts.get(match.player2_id, 0)


def match_intro_seconds_remaining(match: WorldMatch, *, now=None) -> int:
    if not match or match.status != WorldMatch.STATUS_ACTIVE or not match.started_at:
        return 0
    now = now or timezone.now()
    remaining = (match.started_at + timedelta(seconds=MATCH_INTRO_SECONDS) - now).total_seconds()
    return max(0, int(math.ceil(remaining)))


def next_question_index(match: WorldMatch, user):
    if not match.includes(user):
        return None
    p1_count, p2_count = answered_counts(match)
    my_count = p1_count if match.player1_id == user.id else p2_count
    opponent_count = p2_count if match.player1_id == user.id else p1_count
    if my_count >= match.total_questions:
        return None
    # Barrier sync: once a player locks the current answer, they wait until
    # the opponent also answers that same question. Nobody can jump ahead.
    if my_count > opponent_count:
        return None
    return my_count


def issue_question_ticket(match: WorldMatch, user, question_index: int) -> WorldQuestionTicket:
    if match.status != WorldMatch.STATUS_ACTIVE or not match.includes(user):
        raise ValueError("This match is not active for this player.")
    if question_index != next_question_index(match, user):
        raise ValueError("Question is no longer current.")
    pool = get_pool_entry(match, question_index)
    seconds = int(pool.estimated_seconds if pool else QUESTION_TIME_LIMIT_SECONDS)
    seconds = max(20, min(180, seconds))
    now = timezone.now()
    ticket, created = WorldQuestionTicket.objects.get_or_create(
        match=match,
        user=user,
        question_index=question_index,
        defaults={"issued_at": now, "deadline_at": now + timedelta(seconds=seconds)},
    )
    return ticket


def _score_answer(pool: GameQuestionPool | None, *, correct: bool, response_ms: int, integrity_flag: str) -> int:
    if not correct:
        return 0
    difficulty = pool.difficulty if pool else GameQuestionPool.DIFFICULTY_MEDIUM
    base = DIFFICULTY_POINTS.get(difficulty, 120)
    if integrity_flag != WorldAnswer.INTEGRITY_OK:
        return base
    estimate_ms = max(20_000, int((pool.estimated_seconds if pool else QUESTION_TIME_LIMIT_SECONDS) * 1000))
    # 20 bonus points for very fast *plausible* answers, tapering to zero at the estimate.
    speed_ratio = max(0.0, min(1.0, 1.0 - (response_ms / estimate_ms)))
    return base + round(20 * speed_ratio)


def submit_answer_by_token(match: WorldMatch, user, token: str, selected: str):
    if match.status != WorldMatch.STATUS_ACTIVE or not match.includes(user):
        raise ValueError("This match is not active for this player.")
    try:
        ticket = WorldQuestionTicket.objects.select_related("match").get(token=token, match=match, user=user)
    except WorldQuestionTicket.DoesNotExist as exc:
        raise ValueError("Question token is invalid or expired.") from exc
    if ticket.consumed_at:
        raise ValueError("This question was already submitted.")
    if ticket.question_index != next_question_index(match, user):
        raise ValueError("Answer the current question first.")

    question = get_question(match, ticket.question_index)
    pool = get_pool_entry(match, ticket.question_index)
    if question is None:
        raise ValueError("Match question is unavailable.")

    now = timezone.now()
    timed_out = now > ticket.deadline_at
    selected_normalized = normalize_choice(selected)
    if not timed_out and selected_normalized not in {"A", "B", "C", "D"}:
        raise ValueError("Choose A, B, C, or D.")
    response_ms = max(0, round((now - ticket.issued_at).total_seconds() * 1000))
    integrity = WorldAnswer.INTEGRITY_TIMEOUT if timed_out else WorldAnswer.INTEGRITY_OK
    if not timed_out and response_ms < 650:
        integrity = WorldAnswer.INTEGRITY_TOO_FAST
    correct = False if timed_out else answer_is_correct(question, selected)
    points = _score_answer(pool, correct=correct, response_ms=response_ms, integrity_flag=integrity)

    with transaction.atomic():
        locked = WorldMatch.objects.select_for_update().get(pk=match.pk)
        locked_ticket = WorldQuestionTicket.objects.select_for_update().get(pk=ticket.pk)
        if locked_ticket.consumed_at:
            raise ValueError("This question was already submitted.")
        answer, created = WorldAnswer.objects.get_or_create(
            match=locked,
            user=user,
            question_index=ticket.question_index,
            defaults={
                "pool_entry": pool,
                "selected_answer": "" if timed_out else selected.upper(),
                "is_correct": correct,
                "points": points,
                "response_ms": response_ms,
                "integrity_flag": integrity,
                "answered_at": now,
            },
        )
        if not created:
            raise ValueError("This question was already submitted.")
        locked_ticket.consumed_at = now
        locked_ticket.save(update_fields=["consumed_at"])
        if locked.player1_id == user.id:
            locked.player1_score += points
            locked.player1_last_seen_at = now
        else:
            locked.player2_score += points
            locked.player2_last_seen_at = now
        locked.save(update_fields=["player1_score", "player2_score", "player1_last_seen_at", "player2_last_seen_at"])
        if pool:
            GameQuestionPool.objects.filter(pk=pool.pk).update(
                answer_count=F("answer_count") + 1,
                correct_count=F("correct_count") + (1 if correct else 0),
            )
        _maybe_finalize_locked(locked)
        return answer, locked


def submit_answer(match: WorldMatch, user, question_index: int, selected: str):
    """Backward-compatible service API used by existing V50.3 tests."""
    ticket = issue_question_ticket(match, user, question_index)
    return submit_answer_by_token(match, user, ticket.token, selected)


def heartbeat(match: WorldMatch, user):
    if match.status != WorldMatch.STATUS_ACTIVE or not match.includes(user):
        return match
    now = timezone.now()
    if match.player1_id == user.id:
        WorldMatch.objects.filter(pk=match.pk, status=WorldMatch.STATUS_ACTIVE).update(player1_last_seen_at=now)
        match.player1_last_seen_at = now
    else:
        WorldMatch.objects.filter(pk=match.pk, status=WorldMatch.STATUS_ACTIVE).update(player2_last_seen_at=now)
        match.player2_last_seen_at = now
    resolve_disconnect_forfeit(match)
    match.refresh_from_db()
    return match


def resolve_disconnect_forfeit(match: WorldMatch):
    if match.status != WorldMatch.STATUS_ACTIVE or not match.player2_id or not match.started_at:
        return False
    now = timezone.now()
    if (now - match.started_at).total_seconds() < HEARTBEAT_GRACE_SECONDS:
        return False
    p1_seen = match.player1_last_seen_at or match.started_at
    p2_seen = match.player2_last_seen_at or match.started_at
    p1_stale = (now - p1_seen).total_seconds() > HEARTBEAT_STALE_SECONDS
    p2_stale = (now - p2_seen).total_seconds() > HEARTBEAT_STALE_SECONDS
    if p1_stale == p2_stale:
        return False
    loser_id = match.player1_id if p1_stale else match.player2_id
    winner_id = match.player2_id if p1_stale else match.player1_id
    with transaction.atomic():
        locked = WorldMatch.objects.select_for_update().get(pk=match.pk)
        if locked.status != WorldMatch.STATUS_ACTIVE:
            return False
        locked.disconnect_forfeit_user_id = loser_id
        _finalize_locked(locked, forced_winner_id=winner_id)
    return True


def _elo_pair(a: int, b: int, score_a: float, k: int = 24, weight: Decimal | float = 1.0):
    expected_a = 1.0 / (1.0 + math.pow(10.0, (b - a) / 400.0))
    expected_b = 1.0 - expected_a
    weighted_k = float(k) * float(weight)
    new_a = max(100, round(a + weighted_k * (score_a - expected_a)))
    new_b = max(100, round(b + weighted_k * ((1.0 - score_a) - expected_b)))
    return new_a, new_b


def _award_world_xp(match: WorldMatch, user, winner_id):
    if winner_id is None:
        amount, title = 20, "World draw"
    elif winner_id == user.id:
        amount, title = 30, "World victory"
    else:
        amount, title = 15, "World match completed"
    award_xp(
        user,
        amount=amount,
        source_key=f"world-match:{match.pk}:{user.pk}",
        title=title,
        metadata={"match_id": str(match.pk), "subject": match.subject, "mode": match.mode},
    )


def _finalize_locked(match: WorldMatch, forced_winner_id=None):
    if not match.player2_id:
        return False
    if forced_winner_id is not None:
        winner_id = forced_winner_id
        score_a = 1.0 if winner_id == match.player1_id else 0.0
    elif match.player1_score > match.player2_score:
        winner_id = match.player1_id
        score_a = 1.0
    elif match.player2_score > match.player1_score:
        winner_id = match.player2_id
        score_a = 0.0
    else:
        winner_id = None
        score_a = 0.5

    p1_rating = _rating_for(match.player1, match.subject)
    p2_rating = _rating_for(match.player2, match.subject)
    before1, before2 = p1_rating.rating, p2_rating.rating
    after1, after2 = before1, before2

    for rating, won, lost in (
        (p1_rating, winner_id == match.player1_id, winner_id == match.player2_id),
        (p2_rating, winner_id == match.player2_id, winner_id == match.player1_id),
    ):
        if winner_id is None:
            rating.draws += 1
            rating.streak = 0
        elif won:
            rating.wins += 1
            rating.streak = max(1, rating.streak + 1)
        elif lost:
            rating.losses += 1
            rating.streak = min(-1, rating.streak - 1)
        if match.mode == WorldMatch.MODE_RANKED:
            rating.ranked_played += 1

    if match.mode == WorldMatch.MODE_RANKED:
        after1, after2 = _elo_pair(before1, before2, score_a, weight=match.mmr_weight)
        p1_rating.rating, p2_rating.rating = after1, after2

    p1_rating.save(update_fields=["rating", "wins", "losses", "draws", "streak", "ranked_played", "updated_at"])
    p2_rating.save(update_fields=["rating", "wins", "losses", "draws", "streak", "ranked_played", "updated_at"])

    match.status = WorldMatch.STATUS_COMPLETED
    match.winner_id = winner_id
    match.completed_at = timezone.now()
    match.player1_rating_before, match.player2_rating_before = before1, before2
    match.player1_rating_after, match.player2_rating_after = after1, after2
    match.save(update_fields=[
        "status", "winner", "completed_at", "disconnect_forfeit_user",
        "player1_rating_before", "player2_rating_before", "player1_rating_after", "player2_rating_after",
    ])
    _award_world_xp(match, match.player1, winner_id)
    _award_world_xp(match, match.player2, winner_id)
    return True


def _maybe_finalize_locked(match: WorldMatch):
    if not match.player2_id or match.total_questions <= 0:
        return False
    p1_count = WorldAnswer.objects.filter(match=match, user_id=match.player1_id).count()
    p2_count = WorldAnswer.objects.filter(match=match, user_id=match.player2_id).count()
    if p1_count < match.total_questions or p2_count < match.total_questions:
        return False
    return _finalize_locked(match)


MULTIPLAYER_MIN_PLAYERS = 3
MULTIPLAYER_MAX_PLAYERS = 4
MULTIPLAYER_REVEAL_SECONDS = 5
MULTIPLAYER_START_COUNTDOWN_SECONDS = 4
MULTIPLAYER_SWAP_REQUEST_SECONDS = 60
MULTIPLAYER_QUESTION_COUNTS = {5, 10, 15, 20}
MULTIPLAYER_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MULTIPLAYER_PRESENCE_STALE_SECONDS = 30
MULTIPLAYER_RECONNECT_GRACE_SECONDS = 120


def _new_multiplayer_join_code(length: int = 6) -> str:
    for _ in range(30):
        code = "".join(random.choice(MULTIPLAYER_CODE_ALPHABET) for _ in range(length))
        if not WorldMultiplayerRoom.objects.filter(join_code=code).exists():
            return code
    raise RuntimeError("Could not allocate a multiplayer room code.")


def _valid_multiplayer_game_modes() -> set[str]:
    return {choice[0] for choice in WorldMultiplayerRoom.GAME_MODE_CHOICES}


def _team_for_seat(game_mode: str, seat_number: int) -> str:
    if game_mode != WorldMultiplayerRoom.GAME_MODE_TEAM_2V2:
        return WorldMultiplayerSeat.TEAM_NONE
    return WorldMultiplayerSeat.TEAM_A if seat_number in {1, 3} else WorldMultiplayerSeat.TEAM_B


def _bump_multiplayer_state_locked(room: WorldMultiplayerRoom) -> None:
    room.state_version = int(room.state_version or 0) + 1
    room.save(update_fields=["state_version"])


def _transfer_multiplayer_host_locked(room: WorldMultiplayerRoom, *, excluding_user_id: int | None = None) -> bool:
    seats = WorldMultiplayerSeat.objects.filter(room=room, is_active=True)
    if excluding_user_id is not None:
        seats = seats.exclude(user_id=excluding_user_id)
    next_seat = seats.order_by("seat_number", "joined_at").first()
    if not next_seat:
        return False
    if room.host_id == next_seat.user_id:
        return False
    room.host_id = next_seat.user_id
    room.save(update_fields=["host"])
    return True


def multiplayer_room_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    seat = (
        WorldMultiplayerSeat.objects.select_related("room")
        .filter(
            user=user,
            is_active=True,
            room__status__in=[WorldMultiplayerRoom.STATUS_LOBBY, WorldMultiplayerRoom.STATUS_ACTIVE],
        )
        .order_by("-room__created_at")
        .first()
    )
    return seat.room if seat else None


def create_multiplayer_room(
    user,
    *,
    subject: str,
    capacity: int = 4,
    question_count: int = 5,
    access_type: str = WorldMultiplayerRoom.ACCESS_PRIVATE,
    game_mode: str = WorldMultiplayerRoom.GAME_MODE_FFA,
) -> WorldMultiplayerRoom:
    if subject not in {WorldRating.SUBJECT_MATH, WorldRating.SUBJECT_RW}:
        raise ValueError("Invalid subject")
    try:
        capacity = int(capacity)
    except (TypeError, ValueError):
        raise ValueError("Room size must be 3 or 4 players.")
    if capacity not in {WorldMultiplayerRoom.CAPACITY_THREE, WorldMultiplayerRoom.CAPACITY_FOUR}:
        raise ValueError("Room size must be 3 or 4 players.")
    try:
        question_count = int(question_count)
    except (TypeError, ValueError):
        raise ValueError("Question count must be 5, 10, 15, or 20.")
    if question_count not in MULTIPLAYER_QUESTION_COUNTS:
        raise ValueError("Question count must be 5, 10, 15, or 20.")
    access_type = (access_type or WorldMultiplayerRoom.ACCESS_PRIVATE).strip().lower()
    if access_type not in {WorldMultiplayerRoom.ACCESS_PRIVATE, WorldMultiplayerRoom.ACCESS_PUBLIC}:
        raise ValueError("Access type must be private or public.")
    game_mode = (game_mode or WorldMultiplayerRoom.GAME_MODE_FFA).strip().lower()
    if game_mode not in _valid_multiplayer_game_modes():
        raise ValueError("Invalid multiplayer game mode.")
    if game_mode == WorldMultiplayerRoom.GAME_MODE_TEAM_2V2 and capacity != 4:
        raise ValueError("2v2 rooms require exactly 4 seats.")
    existing = multiplayer_room_for_user(user)
    if existing:
        return existing
    ensure_ratings(user)
    with transaction.atomic():
        room = WorldMultiplayerRoom.objects.create(
            host=user,
            subject=subject,
            capacity=capacity,
            question_count=question_count,
            access_type=access_type,
            game_mode=game_mode,
            join_code=_new_multiplayer_join_code(),
        )
        WorldMultiplayerSeat.objects.create(
            room=room,
            user=user,
            seat_number=1,
            team=_team_for_seat(game_mode, 1),
        )
    return room


def join_multiplayer_room(user, *, join_code: str) -> tuple[WorldMultiplayerRoom, WorldMultiplayerSeat, bool]:
    code = (join_code or "").strip().upper()
    if not code:
        raise ValueError("Enter a room code.")
    with transaction.atomic():
        room = WorldMultiplayerRoom.objects.select_for_update().filter(join_code=code).first()
        if not room:
            raise ValueError("Room not found.")
        if room.status != WorldMultiplayerRoom.STATUS_LOBBY:
            raise ValueError("This room is no longer accepting players.")
        existing = WorldMultiplayerSeat.objects.filter(room=room, user=user, is_active=True).first()
        if existing:
            return room, existing, False
        other_room = multiplayer_room_for_user(user)
        if other_room and other_room.pk != room.pk:
            raise ValueError("Leave your current multiplayer room first.")
        occupied = set(
            WorldMultiplayerSeat.objects.filter(room=room, is_active=True).values_list("seat_number", flat=True)
        )
        available = [number for number in range(1, room.capacity + 1) if number not in occupied]
        if not available:
            raise ValueError("Room is full.")
        ensure_ratings(user)
        seat_number = available[0]
        seat = WorldMultiplayerSeat.objects.create(
            room=room,
            user=user,
            seat_number=seat_number,
            team=_team_for_seat(room.game_mode, seat_number),
        )
        _bump_multiplayer_state_locked(room)
        return room, seat, True


@transaction.atomic
def join_public_multiplayer_room(
    user,
    *,
    subject: str,
    capacity: int = 4,
    question_count: int = 5,
    game_mode: str = WorldMultiplayerRoom.GAME_MODE_FFA,
) -> tuple[WorldMultiplayerRoom, WorldMultiplayerSeat, bool]:
    if subject not in {WorldRating.SUBJECT_MATH, WorldRating.SUBJECT_RW}:
        raise ValueError("Invalid subject")
    try:
        capacity = int(capacity)
    except (TypeError, ValueError):
        raise ValueError("Room size must be 3 or 4 players.")
    if capacity not in {WorldMultiplayerRoom.CAPACITY_THREE, WorldMultiplayerRoom.CAPACITY_FOUR}:
        raise ValueError("Room size must be 3 or 4 players.")
    try:
        question_count = int(question_count)
    except (TypeError, ValueError):
        raise ValueError("Question count must be 5, 10, 15, or 20.")
    if question_count not in MULTIPLAYER_QUESTION_COUNTS:
        raise ValueError("Question count must be 5, 10, 15, or 20.")
    game_mode = (game_mode or WorldMultiplayerRoom.GAME_MODE_FFA).strip().lower()
    if game_mode not in _valid_multiplayer_game_modes():
        raise ValueError("Invalid multiplayer game mode.")
    if game_mode == WorldMultiplayerRoom.GAME_MODE_TEAM_2V2 and capacity != 4:
        raise ValueError("2v2 rooms require exactly 4 seats.")

    current = multiplayer_room_for_user(user)
    if current:
        if (
            current.access_type == WorldMultiplayerRoom.ACCESS_PUBLIC
            and current.status == WorldMultiplayerRoom.STATUS_LOBBY
            and current.subject == subject
            and current.capacity == capacity
            and current.question_count == question_count
            and current.game_mode == game_mode
        ):
            seat = WorldMultiplayerSeat.objects.filter(room=current, user=user, is_active=True).first()
            if seat:
                return current, seat, False
        raise ValueError("Leave your current multiplayer room first.")

    rooms = list(
        WorldMultiplayerRoom.objects.select_for_update()
        .filter(
            status=WorldMultiplayerRoom.STATUS_LOBBY,
            access_type=WorldMultiplayerRoom.ACCESS_PUBLIC,
            game_mode=game_mode,
            subject=subject,
            capacity=capacity,
            question_count=question_count,
        )
        .order_by("created_at", "id")
    )
    for room in rooms:
        occupied = set(
            WorldMultiplayerSeat.objects.filter(room=room, is_active=True).values_list("seat_number", flat=True)
        )
        if len(occupied) >= room.capacity:
            continue
        seat_number = min(number for number in range(1, room.capacity + 1) if number not in occupied)
        ensure_ratings(user)
        seat = WorldMultiplayerSeat.objects.create(
            room=room,
            user=user,
            seat_number=seat_number,
            team=_team_for_seat(room.game_mode, seat_number),
        )
        _bump_multiplayer_state_locked(room)
        return room, seat, False

    room = create_multiplayer_room(
        user,
        subject=subject,
        capacity=capacity,
        question_count=question_count,
        access_type=WorldMultiplayerRoom.ACCESS_PUBLIC,
        game_mode=game_mode,
    )
    seat = WorldMultiplayerSeat.objects.get(room=room, user=user, is_active=True)
    return room, seat, True


def set_multiplayer_access_type(room: WorldMultiplayerRoom, host, access_type: str) -> WorldMultiplayerRoom:
    access_type = (access_type or "").strip().lower()
    if access_type not in {WorldMultiplayerRoom.ACCESS_PRIVATE, WorldMultiplayerRoom.ACCESS_PUBLIC}:
        raise ValueError("Access type must be private or public.")
    if room.host_id != host.id:
        raise ValueError("Only the host can change room access.")

    with transaction.atomic():
        locked = WorldMultiplayerRoom.objects.select_for_update().get(pk=room.pk)
        if locked.host_id != host.id:
            raise ValueError("Only the host can change room access.")
        if locked.status != WorldMultiplayerRoom.STATUS_LOBBY:
            raise ValueError("Room access can only change before the battle starts.")
        if locked.access_type != access_type:
            locked.access_type = access_type
            locked.state_version = int(locked.state_version or 0) + 1
            locked.save(update_fields=["access_type", "state_version"])
        return locked


def _maybe_launch_multiplayer_first_round_locked(room: WorldMultiplayerRoom, *, now=None) -> bool:
    """Start Q1 only after every still-active browser has reached the arena.

    ``arena_ready_at`` is set by the first play-page heartbeat. This keeps the
    server timer completely stopped while one browser is still rendering or
    navigating out of the lobby.
    """
    if (
        room.status != WorldMultiplayerRoom.STATUS_ACTIVE
        or int(room.current_question_index or 0) != 0
        or room.question_started_at is not None
    ):
        return False
    seats = list(
        WorldMultiplayerSeat.objects.select_for_update()
        .filter(room=room, is_active=True)
        .only("id", "arena_ready_at")
    )
    if not seats or any(seat.arena_ready_at is None for seat in seats):
        return False
    now = now or timezone.now()
    room.question_started_at = now + timedelta(seconds=MULTIPLAYER_START_COUNTDOWN_SECONDS)
    room.state_version = int(room.state_version or 0) + 1
    room.save(update_fields=["question_started_at", "state_version"])
    return True


def set_multiplayer_ready(room: WorldMultiplayerRoom, user, ready: bool) -> WorldMultiplayerSeat:
    if room.status != WorldMultiplayerRoom.STATUS_LOBBY:
        raise ValueError("Ready state can only change in the lobby.")
    with transaction.atomic():
        locked = WorldMultiplayerRoom.objects.select_for_update().get(pk=room.pk)
        # The caller may have loaded the lobby before another browser started
        # the game. Recheck the *locked* room before changing seat readiness.
        if locked.status != WorldMultiplayerRoom.STATUS_LOBBY:
            raise ValueError("Ready state can only change in the lobby.")
        seat = WorldMultiplayerSeat.objects.select_for_update().filter(room=locked, user=user, is_active=True).first()
        if not seat:
            raise ValueError("You are not in this room.")
        ready = bool(ready)
        now = timezone.now()
        changed = seat.is_ready != ready or not seat.is_connected or seat.disconnected_at is not None
        seat.is_ready = ready
        seat.last_seen_at = now
        seat.is_connected = True
        seat.disconnected_at = None
        seat.save(update_fields=["is_ready", "last_seen_at", "is_connected", "disconnected_at"])
        if changed:
            _bump_multiplayer_state_locked(locked)
        return seat


def touch_multiplayer_presence(room: WorldMultiplayerRoom, user, *, arena_ready: bool = False) -> tuple[WorldMultiplayerRoom, WorldMultiplayerSeat]:
    now = timezone.now()
    with transaction.atomic():
        locked = WorldMultiplayerRoom.objects.select_for_update().get(pk=room.pk)
        seat = WorldMultiplayerSeat.objects.select_for_update().filter(room=locked, user=user, is_active=True).first()
        if not seat:
            raise ValueError("You are no longer an active player in this room.")
        reconnected = not seat.is_connected or seat.disconnected_at is not None
        seat.last_seen_at = now
        seat.is_connected = True
        seat.disconnected_at = None
        update_fields = ["last_seen_at", "is_connected", "disconnected_at"]
        arena_became_ready = bool(arena_ready) and locked.status == WorldMultiplayerRoom.STATUS_ACTIVE and seat.arena_ready_at is None
        if arena_became_ready:
            seat.arena_ready_at = now
            update_fields.append("arena_ready_at")
        seat.save(update_fields=update_fields)
        if reconnected or arena_became_ready:
            _bump_multiplayer_state_locked(locked)
        _maybe_launch_multiplayer_first_round_locked(locked, now=now)
        return locked, seat


def reconcile_multiplayer_presence(room: WorldMultiplayerRoom, *, now=None) -> WorldMultiplayerRoom:
    if room.status not in {WorldMultiplayerRoom.STATUS_LOBBY, WorldMultiplayerRoom.STATUS_ACTIVE}:
        return room
    now = now or timezone.now()
    stale_before = now - timedelta(seconds=MULTIPLAYER_PRESENCE_STALE_SECONDS)
    grace_before = now - timedelta(seconds=MULTIPLAYER_RECONNECT_GRACE_SECONDS)
    with transaction.atomic():
        locked = WorldMultiplayerRoom.objects.select_for_update().get(pk=room.pk)
        if locked.status not in {WorldMultiplayerRoom.STATUS_LOBBY, WorldMultiplayerRoom.STATUS_ACTIVE}:
            return locked
        seats = list(
            WorldMultiplayerSeat.objects.select_for_update()
            .filter(room=locked, is_active=True)
            .order_by("seat_number")
        )
        changed = False
        host_may_need_transfer = False
        for seat in seats:
            if seat.last_seen_at <= stale_before and seat.is_connected:
                seat.is_connected = False
                seat.disconnected_at = seat.disconnected_at or now
                seat.save(update_fields=["is_connected", "disconnected_at"])
                changed = True
            if (
                locked.status == WorldMultiplayerRoom.STATUS_ACTIVE
                and not seat.is_connected
                and seat.disconnected_at
                and seat.disconnected_at <= grace_before
            ):
                seat.is_active = False
                seat.left_at = now
                seat.save(update_fields=["is_active", "left_at"])
                changed = True
                if seat.user_id == locked.host_id:
                    host_may_need_transfer = True
        if host_may_need_transfer:
            _transfer_multiplayer_host_locked(locked)
        if changed:
            _bump_multiplayer_state_locked(locked)
        if locked.status == WorldMultiplayerRoom.STATUS_ACTIVE:
            _maybe_launch_multiplayer_first_round_locked(locked, now=now)
        if changed and locked.status == WorldMultiplayerRoom.STATUS_ACTIVE:
            _advance_multiplayer_locked(locked, now=now)
            locked.refresh_from_db()
        return locked


def multiplayer_can_start(room: WorldMultiplayerRoom) -> bool:
    if room.status != WorldMultiplayerRoom.STATUS_LOBBY:
        return False
    seats = list(WorldMultiplayerSeat.objects.filter(room=room, is_active=True).order_by("seat_number"))
    if len(seats) < MULTIPLAYER_MIN_PLAYERS:
        return False
    if room.game_mode == WorldMultiplayerRoom.GAME_MODE_TEAM_2V2 and len(seats) != 4:
        return False
    return all(seat.is_ready for seat in seats)


def start_multiplayer_room(room: WorldMultiplayerRoom, user) -> WorldMultiplayerRoom:
    if room.host_id != user.id:
        raise ValueError("Only the host can start this room.")
    with transaction.atomic():
        locked = WorldMultiplayerRoom.objects.select_for_update().get(pk=room.pk)
        # Host ownership can change while this request waits on the room lock.
        if locked.host_id != user.id:
            raise ValueError("Only the host can start this room.")
        if locked.status != WorldMultiplayerRoom.STATUS_LOBBY:
            return locked
        live_modes = {
            WorldMultiplayerRoom.GAME_MODE_FFA,
            WorldMultiplayerRoom.GAME_MODE_TEAM_2V2,
        }
        if locked.game_mode not in live_modes:
            raise ValueError("This multiplayer ruleset is prepared but not live yet.")
        seats = list(
            WorldMultiplayerSeat.objects.select_for_update()
            .filter(room=locked, is_active=True)
            .select_related("user")
            .order_by("seat_number")
        )
        if len(seats) < MULTIPLAYER_MIN_PLAYERS:
            raise ValueError("At least 3 players are required.")
        if locked.game_mode == WorldMultiplayerRoom.GAME_MODE_TEAM_2V2:
            if len(seats) != 4:
                raise ValueError("2v2 requires exactly 4 active players.")
            for seat in seats:
                expected_team = _team_for_seat(locked.game_mode, seat.seat_number)
                if seat.team != expected_team:
                    seat.team = expected_team
                    seat.save(update_fields=["team"])
        if not all(seat.is_ready for seat in seats):
            raise ValueError("Every player must be ready before the room starts.")
        requested_count = int(locked.question_count or 5)
        pool_rows = pick_question_pool(locked.subject, [seat.user for seat in seats], requested_count)
        if len(pool_rows) < requested_count:
            raise RuntimeError(f"Not enough verified World questions for a {requested_count}-question battle yet.")
        activation_time = timezone.now()
        locked.question_pool_ids = [row.id for row in pool_rows]
        locked.status = WorldMultiplayerRoom.STATUS_ACTIVE
        locked.started_at = activation_time
        locked.current_question_index = 0
        # Q1 remains fully paused until every active client reaches the play
        # screen and sends its first arena heartbeat. The last arriving client
        # arms a shared visible countdown in ``touch_multiplayer_presence``.
        locked.question_started_at = None
        locked.state_version = int(locked.state_version or 0) + 1
        locked.save(
            update_fields=[
                "question_pool_ids",
                "status",
                "started_at",
                "current_question_index",
                "question_started_at",
                "state_version",
            ]
        )
        WorldMultiplayerSeat.objects.filter(room=locked, is_active=True).update(
            is_connected=True,
            disconnected_at=None,
            last_seen_at=activation_time,
            arena_ready_at=None,
        )
        WorldMultiplayerSeatSwapRequest.objects.filter(
            room=locked, status=WorldMultiplayerSeatSwapRequest.STATUS_PENDING
        ).update(status=WorldMultiplayerSeatSwapRequest.STATUS_CANCELLED, responded_at=activation_time)
        GameQuestionPool.objects.filter(pk__in=locked.question_pool_ids).update(
            times_used=F("times_used") + 1,
            last_used_at=activation_time,
        )
        return locked


def kick_multiplayer_participant(room: WorldMultiplayerRoom, host, user_id: int) -> bool:
    if room.host_id != host.id:
        raise ValueError("Only the host can remove players.")
    if room.status != WorldMultiplayerRoom.STATUS_LOBBY:
        raise ValueError("Players can only be removed before the battle starts.")
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid player.")
    if user_id == room.host_id:
        raise ValueError("The host cannot remove themselves. Use Leave instead.")
    with transaction.atomic():
        locked = WorldMultiplayerRoom.objects.select_for_update().get(pk=room.pk)
        if locked.host_id != host.id:
            raise ValueError("Only the host can remove players.")
        if locked.status != WorldMultiplayerRoom.STATUS_LOBBY:
            raise ValueError("Players can only be removed before the battle starts.")
        if user_id == locked.host_id:
            raise ValueError("The host cannot remove themselves. Use Leave instead.")
        seat = WorldMultiplayerSeat.objects.select_for_update().filter(room=locked, user_id=user_id, is_active=True).first()
        if not seat:
            raise ValueError("Player is no longer in this room.")
        WorldMultiplayerSeatSwapRequest.objects.filter(
            room=locked, status=WorldMultiplayerSeatSwapRequest.STATUS_PENDING
        ).filter(Q(requester_id=user_id) | Q(target_id=user_id)).update(
            status=WorldMultiplayerSeatSwapRequest.STATUS_CANCELLED, responded_at=timezone.now()
        )
        seat.delete()
        _bump_multiplayer_state_locked(locked)
        return True


def leave_multiplayer_room(room: WorldMultiplayerRoom, user) -> bool:
    if room.status not in {WorldMultiplayerRoom.STATUS_LOBBY, WorldMultiplayerRoom.STATUS_ACTIVE}:
        raise ValueError("This room is already closed.")
    now = timezone.now()
    with transaction.atomic():
        locked = WorldMultiplayerRoom.objects.select_for_update().get(pk=room.pk)
        seat = WorldMultiplayerSeat.objects.select_for_update().filter(room=locked, user=user, is_active=True).first()
        if not seat:
            return False

        if locked.status == WorldMultiplayerRoom.STATUS_LOBBY:
            leaving_host = locked.host_id == user.id
            WorldMultiplayerSeatSwapRequest.objects.filter(
                room=locked, status=WorldMultiplayerSeatSwapRequest.STATUS_PENDING
            ).filter(Q(requester=user) | Q(target=user)).update(
                status=WorldMultiplayerSeatSwapRequest.STATUS_CANCELLED, responded_at=now
            )
            seat.delete()
            remaining = WorldMultiplayerSeat.objects.filter(room=locked, is_active=True).order_by("seat_number")
            if leaving_host:
                next_seat = remaining.first()
                if next_seat:
                    locked.host_id = next_seat.user_id
                    locked.state_version = int(locked.state_version or 0) + 1
                    locked.save(update_fields=["host", "state_version"])
                else:
                    locked.status = WorldMultiplayerRoom.STATUS_CANCELLED
                    locked.state_version = int(locked.state_version or 0) + 1
                    locked.save(update_fields=["status", "state_version"])
            else:
                _bump_multiplayer_state_locked(locked)
            return True

        # Active FFA battles survive individual departures. Keep the seat row for
        # final score/history, but remove it from the live barrier and room access.
        seat.is_active = False
        seat.is_connected = False
        seat.disconnected_at = seat.disconnected_at or now
        seat.left_at = now
        seat.save(update_fields=["is_active", "is_connected", "disconnected_at", "left_at"])
        if locked.host_id == user.id:
            _transfer_multiplayer_host_locked(locked, excluding_user_id=user.id)
        _bump_multiplayer_state_locked(locked)
        WorldMultiplayerQuestionTicket.objects.filter(
            room=locked,
            user=user,
            consumed_at__isnull=True,
        ).update(consumed_at=now)
        _advance_multiplayer_locked(locked, now=now)
        return True



def _expire_multiplayer_swap_requests(room: WorldMultiplayerRoom, *, now=None) -> None:
    now = now or timezone.now()
    cutoff = now - timedelta(seconds=MULTIPLAYER_SWAP_REQUEST_SECONDS)
    WorldMultiplayerSeatSwapRequest.objects.filter(
        room=room,
        status=WorldMultiplayerSeatSwapRequest.STATUS_PENDING,
        created_at__lt=cutoff,
    ).update(status=WorldMultiplayerSeatSwapRequest.STATUS_EXPIRED, responded_at=now)


def request_multiplayer_seat_swap(room: WorldMultiplayerRoom, requester, target_user_id: int) -> WorldMultiplayerSeatSwapRequest:
    if room.status != WorldMultiplayerRoom.STATUS_LOBBY:
        raise ValueError("Seats can only be changed before the battle starts.")
    if room.game_mode != WorldMultiplayerRoom.GAME_MODE_TEAM_2V2:
        raise ValueError("Seat swap requests are only available in 2v2 rooms.")
    try:
        target_user_id = int(target_user_id)
    except (TypeError, ValueError):
        raise ValueError("Choose a valid player.")
    if requester.id == target_user_id:
        raise ValueError("Choose another player.")

    now = timezone.now()
    with transaction.atomic():
        locked = WorldMultiplayerRoom.objects.select_for_update().get(pk=room.pk)
        if locked.status != WorldMultiplayerRoom.STATUS_LOBBY:
            raise ValueError("Seats can only be changed before the battle starts.")
        if locked.game_mode != WorldMultiplayerRoom.GAME_MODE_TEAM_2V2:
            raise ValueError("Seat swap requests are only available in 2v2 rooms.")
        _expire_multiplayer_swap_requests(locked, now=now)
        requester_seat = WorldMultiplayerSeat.objects.select_for_update().filter(
            room=locked, user=requester, is_active=True
        ).first()
        target_seat = WorldMultiplayerSeat.objects.select_for_update().filter(
            room=locked, user_id=target_user_id, is_active=True
        ).first()
        if not requester_seat or not target_seat:
            raise ValueError("Both players must still be in the lobby.")
        busy = WorldMultiplayerSeatSwapRequest.objects.filter(
            room=locked,
            status=WorldMultiplayerSeatSwapRequest.STATUS_PENDING,
        ).filter(
            Q(requester_id__in=[requester.id, target_user_id])
            | Q(target_id__in=[requester.id, target_user_id])
        )
        if busy.exists():
            raise ValueError("One of these players already has a pending seat request.")
        swap = WorldMultiplayerSeatSwapRequest.objects.create(
            room=locked,
            requester=requester,
            target_id=target_user_id,
        )
        _bump_multiplayer_state_locked(locked)
        return swap


def respond_multiplayer_seat_swap(
    room: WorldMultiplayerRoom,
    user,
    request_id,
    *,
    accept: bool,
) -> WorldMultiplayerSeatSwapRequest:
    try:
        request_id = uuid.UUID(str(request_id))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("Invalid seat request.")
    now = timezone.now()
    with transaction.atomic():
        locked = WorldMultiplayerRoom.objects.select_for_update().get(pk=room.pk)
        if locked.status != WorldMultiplayerRoom.STATUS_LOBBY:
            raise ValueError("Seats can only be changed before the battle starts.")
        _expire_multiplayer_swap_requests(locked, now=now)
        swap = WorldMultiplayerSeatSwapRequest.objects.select_for_update().filter(
            pk=request_id,
            room=locked,
            status=WorldMultiplayerSeatSwapRequest.STATUS_PENDING,
        ).first()
        if not swap:
            raise ValueError("This seat request is no longer active.")
        if swap.target_id != user.id:
            raise ValueError("Only the invited player can answer this request.")

        if not accept:
            swap.status = WorldMultiplayerSeatSwapRequest.STATUS_DECLINED
            swap.responded_at = now
            swap.save(update_fields=["status", "responded_at"])
            _bump_multiplayer_state_locked(locked)
            return swap

        requester_seat = WorldMultiplayerSeat.objects.select_for_update().filter(
            room=locked, user_id=swap.requester_id, is_active=True
        ).first()
        target_seat = WorldMultiplayerSeat.objects.select_for_update().filter(
            room=locked, user_id=swap.target_id, is_active=True
        ).first()
        if not requester_seat or not target_seat:
            swap.status = WorldMultiplayerSeatSwapRequest.STATUS_EXPIRED
            swap.responded_at = now
            swap.save(update_fields=["status", "responded_at"])
            raise ValueError("One of the players left the lobby.")

        requester_number = requester_seat.seat_number
        target_number = target_seat.seat_number
        requester_seat.seat_number = target_number
        target_seat.seat_number = requester_number
        requester_seat.team = _team_for_seat(locked.game_mode, requester_seat.seat_number)
        target_seat.team = _team_for_seat(locked.game_mode, target_seat.seat_number)
        requester_seat.is_ready = False
        target_seat.is_ready = False
        requester_seat.save(update_fields=["seat_number", "team", "is_ready"])
        target_seat.save(update_fields=["seat_number", "team", "is_ready"])

        swap.status = WorldMultiplayerSeatSwapRequest.STATUS_ACCEPTED
        swap.responded_at = now
        swap.save(update_fields=["status", "responded_at"])
        WorldMultiplayerSeatSwapRequest.objects.filter(
            room=locked,
            status=WorldMultiplayerSeatSwapRequest.STATUS_PENDING,
        ).filter(
            Q(requester_id__in=[swap.requester_id, swap.target_id])
            | Q(target_id__in=[swap.requester_id, swap.target_id])
        ).exclude(pk=swap.pk).update(
            status=WorldMultiplayerSeatSwapRequest.STATUS_CANCELLED,
            responded_at=now,
        )
        _bump_multiplayer_state_locked(locked)
        return swap


def cancel_multiplayer_seat_swap(room: WorldMultiplayerRoom, user, request_id) -> WorldMultiplayerSeatSwapRequest:
    try:
        request_id = uuid.UUID(str(request_id))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("Invalid seat request.")
    now = timezone.now()
    with transaction.atomic():
        locked = WorldMultiplayerRoom.objects.select_for_update().get(pk=room.pk)
        swap = WorldMultiplayerSeatSwapRequest.objects.select_for_update().filter(
            pk=request_id,
            room=locked,
            status=WorldMultiplayerSeatSwapRequest.STATUS_PENDING,
            requester=user,
        ).first()
        if not swap:
            raise ValueError("This seat request is no longer active.")
        swap.status = WorldMultiplayerSeatSwapRequest.STATUS_CANCELLED
        swap.responded_at = now
        swap.save(update_fields=["status", "responded_at"])
        _bump_multiplayer_state_locked(locked)
        return swap


def _multiplayer_swap_payload(room: WorldMultiplayerRoom, viewer) -> tuple[dict | None, dict | None]:
    if not viewer or room.status != WorldMultiplayerRoom.STATUS_LOBBY or room.game_mode != WorldMultiplayerRoom.GAME_MODE_TEAM_2V2:
        return None, None
    now = timezone.now()
    _expire_multiplayer_swap_requests(room, now=now)
    pending = list(
        WorldMultiplayerSeatSwapRequest.objects.filter(
            room=room,
            status=WorldMultiplayerSeatSwapRequest.STATUS_PENDING,
        ).filter(Q(requester=viewer) | Q(target=viewer)).select_related("requester", "target")
    )
    incoming = next((row for row in pending if row.target_id == viewer.id), None)
    outgoing = next((row for row in pending if row.requester_id == viewer.id), None)

    def pack(row, incoming_side=False):
        if not row:
            return None
        other = row.requester if incoming_side else row.target
        other_seat = WorldMultiplayerSeat.objects.filter(room=room, user=other, is_active=True).first()
        my_seat = WorldMultiplayerSeat.objects.filter(room=room, user=viewer, is_active=True).first()
        display = other.get_full_name() or other.username
        remaining = max(0, MULTIPLAYER_SWAP_REQUEST_SECONDS - int((now - row.created_at).total_seconds()))
        return {
            "id": str(row.id),
            "other_user_id": other.id,
            "other_name": display,
            "other_initials": "".join(part[:1] for part in display.split()[:2]).upper() or other.username[:1].upper(),
            "other_seat": other_seat.seat_number if other_seat else None,
            "my_seat": my_seat.seat_number if my_seat else None,
            "seconds_remaining": remaining,
        }

    return pack(incoming, incoming_side=True), pack(outgoing, incoming_side=False)

def multiplayer_room_payload(room: WorldMultiplayerRoom, *, viewer=None) -> dict:
    room = reconcile_multiplayer_presence(room)
    room.refresh_from_db()
    seats = list(room.seats.select_related("user").order_by("seat_number"))
    active_seats = [seat for seat in seats if seat.is_active]
    seat_map = {seat.seat_number: seat for seat in seats}
    payload_seats = []
    for number in range(1, room.capacity + 1):
        seat = seat_map.get(number)
        if not seat:
            payload_seats.append({"seat_number": number, "occupied": False})
            continue
        display = seat.user.get_full_name() or seat.user.username
        if not seat.is_active:
            presence = "left"
        elif seat.is_connected:
            presence = "connected"
        else:
            presence = "reconnecting"
        payload_seats.append({
            "seat_number": number,
            "occupied": True,
            "user_id": seat.user_id,
            "username": seat.user.username,
            "name": display,
            "initials": "".join(part[:1] for part in display.split()[:2]).upper() or seat.user.username[:1].upper(),
            "is_ready": seat.is_ready,
            "score": seat.score,
            "team": seat.team,
            "is_active": seat.is_active,
            "is_connected": seat.is_connected,
            "presence": presence,
            "is_host": seat.user_id == room.host_id,
            "is_me": bool(viewer and viewer.id == seat.user_id),
        })
    is_team_mode = room.game_mode == WorldMultiplayerRoom.GAME_MODE_TEAM_2V2
    team_standings = _multiplayer_team_rows(room, viewer=viewer) if is_team_mode else []
    my_team = ""
    my_ready = False
    if viewer:
        my_seat = next((seat for seat in seats if seat.user_id == viewer.id and seat.is_active), None)
        if my_seat:
            my_ready = bool(my_seat.is_ready)
            if is_team_mode:
                my_team = my_seat.team
    swap_incoming, swap_outgoing = _multiplayer_swap_payload(room, viewer)
    return {
        "id": str(room.id),
        "join_code": room.join_code,
        "subject": room.subject,
        "subject_label": room.get_subject_display(),
        "capacity": room.capacity,
        "access_type": room.access_type,
        "access_label": room.get_access_type_display(),
        "is_public": room.access_type == WorldMultiplayerRoom.ACCESS_PUBLIC,
        "game_mode": room.game_mode,
        "game_mode_label": room.get_game_mode_display(),
        "is_team_mode": is_team_mode,
        "team_standings": team_standings,
        "my_team": my_team,
        "my_ready": my_ready,
        "swap_incoming": swap_incoming,
        "swap_outgoing": swap_outgoing,
        "state_version": int(room.state_version or 0),
        "status": room.status,
        "occupied": len(active_seats),
        "ready": sum(1 for seat in active_seats if seat.is_ready),
        "connected": sum(1 for seat in active_seats if seat.is_connected),
        "arena_ready": sum(1 for seat in active_seats if seat.arena_ready_at is not None),
        "can_start": multiplayer_can_start(room),
        "is_host": bool(viewer and viewer.id == room.host_id),
        "seats": payload_seats,
        "question_count": int(room.question_count or 5),
        "live_question_count": len(room.question_pool_ids or []),
    }

def get_multiplayer_pool_entry(room: WorldMultiplayerRoom, index: int):
    ids = room.question_pool_ids or []
    if index < 0 or index >= len(ids):
        return None
    try:
        pool_id = ids[index]
    except (IndexError, TypeError):
        return None
    return GameQuestionPool.objects.select_related("math_question", "english_question").filter(pk=pool_id).first()


def get_multiplayer_question(room: WorldMultiplayerRoom, index: int):
    pool = get_multiplayer_pool_entry(room, index)
    return pool.question if pool else None


def multiplayer_question_time_limit(room: WorldMultiplayerRoom, index: int) -> int:
    pool = get_multiplayer_pool_entry(room, index)
    seconds = int(pool.estimated_seconds if pool else QUESTION_TIME_LIMIT_SECONDS)
    return max(20, min(180, seconds))


def multiplayer_answered_user_ids(room: WorldMultiplayerRoom, index: int) -> set[int]:
    active_user_ids = WorldMultiplayerSeat.objects.filter(room=room, is_active=True).values_list("user_id", flat=True)
    return set(
        WorldMultiplayerAnswer.objects.filter(
            room=room,
            question_index=index,
            user_id__in=active_user_ids,
        ).values_list("user_id", flat=True)
    )


def issue_multiplayer_question_ticket(room: WorldMultiplayerRoom, user) -> WorldMultiplayerQuestionTicket:
    if room.status != WorldMultiplayerRoom.STATUS_ACTIVE or not room.includes(user):
        raise ValueError("This multiplayer room is not active for this player.")
    index = int(room.current_question_index or 0)
    if index >= len(room.question_pool_ids or []):
        raise ValueError("There is no current question.")
    if WorldMultiplayerAnswer.objects.filter(room=room, user=user, question_index=index).exists():
        raise ValueError("This question was already submitted.")
    now = timezone.now()
    started = room.question_started_at
    if started is None:
        raise ValueError("Arena is still synchronizing players.")
    if now < started:
        raise ValueError("Round results are being shown.")
    deadline = started + timedelta(seconds=multiplayer_question_time_limit(room, index))
    ticket, _ = WorldMultiplayerQuestionTicket.objects.get_or_create(
        room=room,
        user=user,
        question_index=index,
        defaults={"issued_at": started, "deadline_at": deadline},
    )
    return ticket


def _complete_multiplayer_locked(room: WorldMultiplayerRoom, now=None):
    now = now or timezone.now()
    room.status = WorldMultiplayerRoom.STATUS_COMPLETED
    room.completed_at = now
    room.question_started_at = None
    room.state_version = int(room.state_version or 0) + 1
    room.save(update_fields=["status", "completed_at", "question_started_at", "state_version"])


def _advance_multiplayer_locked(room: WorldMultiplayerRoom, *, now=None) -> bool:
    now = now or timezone.now()
    index = int(room.current_question_index or 0)
    seat_ids = list(
        WorldMultiplayerSeat.objects.filter(room=room, is_active=True).values_list("user_id", flat=True)
    )
    if not seat_ids:
        _complete_multiplayer_locked(room, now)
        return True
    answered = WorldMultiplayerAnswer.objects.filter(room=room, question_index=index, user_id__in=seat_ids).count()
    if answered < len(seat_ids):
        return False
    next_index = index + 1
    if next_index >= len(room.question_pool_ids or []):
        _complete_multiplayer_locked(room, now)
        return True
    room.current_question_index = next_index
    room.question_started_at = now + timedelta(seconds=MULTIPLAYER_REVEAL_SECONDS)
    room.state_version = int(room.state_version or 0) + 1
    room.save(update_fields=["current_question_index", "question_started_at", "state_version"])
    return True


def expire_multiplayer_question_if_needed(room: WorldMultiplayerRoom) -> WorldMultiplayerRoom:
    if room.status != WorldMultiplayerRoom.STATUS_ACTIVE:
        return room
    now = timezone.now()
    index = int(room.current_question_index or 0)
    started = room.question_started_at
    if started is None:
        # Q1 has not been armed yet because at least one active browser has not
        # reached the arena. Never fall back to ``started_at`` here: doing so
        # would burn question time behind navigation/rendering.
        return room
    if now < started:
        return room
    deadline = started + timedelta(seconds=multiplayer_question_time_limit(room, index))
    if now <= deadline:
        return room
    with transaction.atomic():
        locked = WorldMultiplayerRoom.objects.select_for_update().get(pk=room.pk)
        if locked.status != WorldMultiplayerRoom.STATUS_ACTIVE or locked.current_question_index != index:
            return locked
        seats = list(
            WorldMultiplayerSeat.objects.select_for_update()
            .filter(room=locked, is_active=True)
            .select_related("user")
        )
        answered = multiplayer_answered_user_ids(locked, index)
        pool = get_multiplayer_pool_entry(locked, index)
        for seat in seats:
            if seat.user_id in answered:
                continue
            WorldMultiplayerAnswer.objects.create(
                room=locked,
                user=seat.user,
                question_index=index,
                pool_entry=pool,
                selected_answer="",
                is_correct=False,
                points=0,
                response_ms=max(0, round((now - started).total_seconds() * 1000)),
                integrity_flag=WorldMultiplayerAnswer.INTEGRITY_TIMEOUT,
                answered_at=now,
            )
            WorldMultiplayerQuestionTicket.objects.filter(
                room=locked, user=seat.user, question_index=index, consumed_at__isnull=True
            ).update(consumed_at=now)
        _advance_multiplayer_locked(locked, now=now)
        return locked


def submit_multiplayer_answer(room: WorldMultiplayerRoom, user, token: str, selected: str):
    if room.status != WorldMultiplayerRoom.STATUS_ACTIVE or not room.includes(user):
        raise ValueError("This multiplayer room is not active for this player.")
    try:
        ticket = WorldMultiplayerQuestionTicket.objects.get(token=token, room=room, user=user)
    except WorldMultiplayerQuestionTicket.DoesNotExist as exc:
        raise ValueError("Question token is invalid or expired.") from exc
    index = int(room.current_question_index or 0)
    if ticket.question_index != index:
        raise ValueError("Question is no longer current.")
    if ticket.consumed_at or WorldMultiplayerAnswer.objects.filter(room=room, user=user, question_index=index).exists():
        raise ValueError("This question was already submitted.")
    selected_normalized = normalize_choice(selected)
    now = timezone.now()
    timed_out = now > ticket.deadline_at
    if not timed_out and selected_normalized not in {"A", "B", "C", "D"}:
        raise ValueError("Choose A, B, C, or D.")
    question = get_multiplayer_question(room, index)
    pool = get_multiplayer_pool_entry(room, index)
    if question is None:
        raise ValueError("Multiplayer question is unavailable.")
    response_ms = max(0, round((now - ticket.issued_at).total_seconds() * 1000))
    integrity = WorldMultiplayerAnswer.INTEGRITY_TIMEOUT if timed_out else WorldMultiplayerAnswer.INTEGRITY_OK
    if not timed_out and response_ms < 650:
        integrity = WorldMultiplayerAnswer.INTEGRITY_TOO_FAST
    correct = False if timed_out else answer_is_correct(question, selected)
    scoring_integrity = WorldAnswer.INTEGRITY_TIMEOUT if timed_out else (
        WorldAnswer.INTEGRITY_TOO_FAST if integrity == WorldMultiplayerAnswer.INTEGRITY_TOO_FAST else WorldAnswer.INTEGRITY_OK
    )
    points = _score_answer(pool, correct=correct, response_ms=response_ms, integrity_flag=scoring_integrity)
    with transaction.atomic():
        locked = WorldMultiplayerRoom.objects.select_for_update().get(pk=room.pk)
        locked_ticket = WorldMultiplayerQuestionTicket.objects.select_for_update().get(pk=ticket.pk)
        active_seat = (
            WorldMultiplayerSeat.objects.select_for_update()
            .filter(room=locked, user=user, is_active=True)
            .first()
        )
        if locked.status != WorldMultiplayerRoom.STATUS_ACTIVE or locked.current_question_index != index:
            raise ValueError("Question is no longer current.")
        if not active_seat:
            raise ValueError("You are no longer an active player in this room.")
        if locked_ticket.consumed_at:
            raise ValueError("This question was already submitted.")
        answer = WorldMultiplayerAnswer.objects.create(
            room=locked,
            user=user,
            question_index=index,
            pool_entry=pool,
            selected_answer="" if timed_out else selected.upper(),
            is_correct=correct,
            points=points,
            response_ms=response_ms,
            integrity_flag=integrity,
            answered_at=now,
        )
        locked_ticket.consumed_at = now
        locked_ticket.save(update_fields=["consumed_at"])
        WorldMultiplayerSeat.objects.filter(room=locked, user=user, is_active=True).update(
            score=F("score") + points,
            last_seen_at=now,
            is_connected=True,
            disconnected_at=None,
        )
        if pool:
            GameQuestionPool.objects.filter(pk=pool.pk).update(
                answer_count=F("answer_count") + 1,
                correct_count=F("correct_count") + (1 if correct else 0),
            )
        advanced = _advance_multiplayer_locked(locked, now=now)
        if not advanced:
            _bump_multiplayer_state_locked(locked)
        locked.refresh_from_db()
        return answer, locked, advanced


def _multiplayer_reveal_ranking(room: WorldMultiplayerRoom, completed_index: int) -> list[dict]:
    seats = list(WorldMultiplayerSeat.objects.filter(room=room).select_related("user").order_by("seat_number"))
    answers = {
        row.user_id: row
        for row in WorldMultiplayerAnswer.objects.filter(room=room, question_index=completed_index)
    }
    current_rows = []
    previous_rows = []
    for seat in seats:
        answer = answers.get(seat.user_id)
        last_points = int(answer.points if answer else 0)
        display = seat.user.get_full_name() or seat.user.username
        row = {
            "user_id": seat.user_id,
            "name": display,
            "initials": "".join(part[:1] for part in display.split()[:2]).upper() or seat.user.username[:1].upper(),
            "score": int(seat.score),
            "last_points": last_points,
            "is_correct": bool(answer and answer.is_correct),
            "previous_score": max(0, int(seat.score) - last_points),
        }
        current_rows.append(row)
        previous_rows.append(row)
    previous_sorted = sorted(previous_rows, key=lambda row: (-row["previous_score"], row["user_id"]))
    previous_rank = {row["user_id"]: i + 1 for i, row in enumerate(previous_sorted)}
    ranked = sorted(current_rows, key=lambda row: (-row["score"], row["user_id"]))
    for index, row in enumerate(ranked, 1):
        row["rank"] = index
        row["previous_rank"] = previous_rank.get(row["user_id"], index)
        row["movement"] = row["previous_rank"] - index
    return ranked


def _multiplayer_team_rows(
    room: WorldMultiplayerRoom,
    completed_index: int | None = None,
    *,
    viewer=None,
) -> list[dict]:
    seats = list(
        WorldMultiplayerSeat.objects.filter(room=room)
        .select_related("user")
        .order_by("seat_number")
    )
    answers = {}
    if completed_index is not None:
        answers = {
            row.user_id: row
            for row in WorldMultiplayerAnswer.objects.filter(room=room, question_index=completed_index)
        }
    rows = []
    for team, label in (
        (WorldMultiplayerSeat.TEAM_A, "Team A"),
        (WorldMultiplayerSeat.TEAM_B, "Team B"),
    ):
        members = []
        team_score = 0
        team_last_points = 0
        for seat in seats:
            if seat.team != team:
                continue
            answer = answers.get(seat.user_id)
            last_points = int(answer.points if answer else 0)
            display = seat.user.get_full_name() or seat.user.username
            member = {
                "user_id": seat.user_id,
                "name": display,
                "initials": "".join(part[:1] for part in display.split()[:2]).upper() or seat.user.username[:1].upper(),
                "score": int(seat.score),
                "last_points": last_points,
                "is_correct": bool(answer and answer.is_correct),
                "is_active": seat.is_active,
                "is_connected": seat.is_connected,
                "is_me": bool(viewer and viewer.id == seat.user_id),
            }
            members.append(member)
            team_score += int(seat.score)
            team_last_points += last_points
        rows.append({
            "team": team,
            "label": label,
            "score": team_score,
            "last_points": team_last_points,
            "previous_score": max(0, team_score - team_last_points),
            "members": members,
            "is_my_team": bool(viewer and any(member["is_me"] for member in members)),
        })

    previous_sorted = sorted(rows, key=lambda row: (-row["previous_score"], row["team"]))
    previous_rank = {row["team"]: index + 1 for index, row in enumerate(previous_sorted)}
    ranked = sorted(rows, key=lambda row: (-row["score"], row["team"]))
    for index, row in enumerate(ranked, 1):
        row["rank"] = index
        row["previous_rank"] = previous_rank.get(row["team"], index)
        row["movement"] = row["previous_rank"] - index
    if len(ranked) == 2 and ranked[0]["score"] == ranked[1]["score"]:
        for row in ranked:
            row["is_tied"] = True
            row["rank"] = 1
            row["movement"] = 0
    else:
        for row in ranked:
            row["is_tied"] = False
    return ranked


def multiplayer_play_payload(room: WorldMultiplayerRoom, *, viewer=None, include_question=False) -> dict:
    room = reconcile_multiplayer_presence(room)
    room = expire_multiplayer_question_if_needed(room)
    room.refresh_from_db()
    payload = multiplayer_room_payload(room, viewer=viewer)
    now = timezone.now()
    index = int(room.current_question_index or 0)
    started = room.question_started_at
    launch_waiting = bool(
        room.status == WorldMultiplayerRoom.STATUS_ACTIVE
        and index == 0
        and started is None
    )
    opening_countdown = bool(
        room.status == WorldMultiplayerRoom.STATUS_ACTIVE
        and index == 0
        and started
        and now < started
    )
    round_reveal = bool(
        room.status == WorldMultiplayerRoom.STATUS_ACTIVE
        and index > 0
        and started
        and now < started
    )
    reveal_ranking = _multiplayer_reveal_ranking(room, index - 1) if round_reveal else []
    if viewer and reveal_ranking:
        for row in reveal_ranking:
            row["is_me"] = row["user_id"] == viewer.id
    team_reveal = []
    if payload.get("is_team_mode") and round_reveal:
        team_reveal = _multiplayer_team_rows(room, index - 1, viewer=viewer)
    team_result = None
    if payload.get("is_team_mode") and room.status == WorldMultiplayerRoom.STATUS_COMPLETED:
        final_teams = payload.get("team_standings") or []
        if len(final_teams) == 2 and final_teams[0]["score"] == final_teams[1]["score"]:
            team_result = "draw"
        elif final_teams:
            team_result = final_teams[0]["team"]
    payload.update({
        "current_question_index": room.current_question_index,
        "question_number": (index + 1) if room.status == WorldMultiplayerRoom.STATUS_ACTIVE else None,
        "total_questions": len(room.question_pool_ids or []),
        "play_ready": room.status in {WorldMultiplayerRoom.STATUS_ACTIVE, WorldMultiplayerRoom.STATUS_COMPLETED},
        "launch_waiting": launch_waiting,
        "opening_countdown": opening_countdown,
        "start_seconds_remaining": max(1, math.ceil((started - now).total_seconds())) if opening_countdown else 0,
        "round_reveal": round_reveal,
        "reveal_seconds_remaining": max(0, math.ceil((started - now).total_seconds())) if round_reveal else 0,
        "reveal_ranking": reveal_ranking,
        "team_reveal": team_reveal,
        "team_result": team_result,
    })
    if room.status == WorldMultiplayerRoom.STATUS_ACTIVE and not launch_waiting and not round_reveal and not opening_countdown:
        answered_ids = multiplayer_answered_user_ids(room, index)
        payload["answered"] = len(answered_ids)
        payload["waiting_for_others"] = bool(viewer and viewer.id in answered_ids)
        started = room.question_started_at or now
        limit = multiplayer_question_time_limit(room, index)
        payload["seconds_remaining"] = max(0, math.ceil((started + timedelta(seconds=limit) - now).total_seconds()))
    else:
        payload["answered"] = 0
        payload["waiting_for_others"] = False
        payload["seconds_remaining"] = 0
    if include_question and room.status == WorldMultiplayerRoom.STATUS_ACTIVE and viewer and not launch_waiting and not round_reveal and not opening_countdown:
        question = get_multiplayer_question(room, index)
        pool = get_multiplayer_pool_entry(room, index)
        if question and viewer.id not in multiplayer_answered_user_ids(room, index):
            ticket = issue_multiplayer_question_ticket(room, viewer)
            payload["question"] = {
                "text": question.question,
                "a": question.a,
                "b": question.b,
                "c": question.c,
                "d": question.d,
                # Display HTML: MakonBook-format text rendered, legacy text escaped.
                "passage_html": str(question_display(question, "passage")),
                "text_html": str(question_display(question, "question")),
                "a_html": str(question_display(question, "a", inline=True)),
                "b_html": str(question_display(question, "b", inline=True)),
                "c_html": str(question_display(question, "c", inline=True)),
                "d_html": str(question_display(question, "d", inline=True)),
                "difficulty": pool.difficulty if pool else "medium",
                "token": ticket.token,
                "seconds_remaining": max(0, int((ticket.deadline_at - now).total_seconds())),
            }
        else:
            payload["question"] = None
    return payload

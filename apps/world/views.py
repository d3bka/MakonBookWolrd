from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from apps.gamification.models import GamificationProfile, UserAchievement
from apps.gamification.services import level_snapshot
from apps.sat.models import MakonNotification
from apps.sat.student_workspace import should_use_student_workspace

from .models import WorldMatch, WorldRating, WorldMultiplayerRoom, WorldMultiplayerSeat
from .services import (
    QUEUE_MAX_SECONDS,
    active_match_for_user,
    accept_rematch_invite,
    answered_counts,
    cancel_waiting_match,
    create_rematch_invite,
    decline_rematch_invite,
    expire_waiting_match,
    ensure_ratings,
    get_pool_entry,
    get_question,
    heartbeat,
    incoming_rematch_invite,
    issue_question_ticket,
    join_queue,
    leaderboard,
    match_intro_seconds_remaining,
    next_question_index,
    queue_seconds_remaining,
    rating_rank,
    reconcile_waiting_match,
    resolve_disconnect_forfeit,
    submit_answer_by_token,
    create_multiplayer_room,
    join_multiplayer_room,
    set_multiplayer_ready,
    start_multiplayer_room,
    leave_multiplayer_room,
    kick_multiplayer_participant,
    multiplayer_room_payload,
    multiplayer_room_for_user,
    multiplayer_play_payload,
    submit_multiplayer_answer,
    join_public_multiplayer_room,
    set_multiplayer_access_type,
    touch_multiplayer_presence,
    request_multiplayer_seat_swap,
    respond_multiplayer_seat_swap,
    cancel_multiplayer_seat_swap,
)


def _student_only(request):
    return should_use_student_workspace(request.user)


def _world_context(user, *, subject=WorldRating.SUBJECT_MATH):
    ratings = ensure_ratings(user)
    selected = ratings[subject]
    math_rating = ratings[WorldRating.SUBJECT_MATH]
    rw_rating = ratings[WorldRating.SUBJECT_RW]
    return {
        "student_workspace_active": "world",
        "world_math_rating": math_rating,
        "world_rw_rating": rw_rating,
        "world_math_rank": rating_rank(math_rating),
        "world_rw_rank": rating_rank(rw_rating),
        "world_selected_rating": selected,
        "world_selected_rank": rating_rank(selected),
        "world_subject": subject,
        "world_csrf_cookie_name": settings.CSRF_COOKIE_NAME,
    }


def _leaderboard_payload(row, *, user):
    display = row.user.get_full_name() or row.user.username
    initials = "".join(part[:1] for part in display.split()[:2]).upper() or row.user.username[:1].upper()
    return {
        "rank": rating_rank(row),
        "name": display,
        "username": row.user.username,
        "initials": initials,
        "tier": row.tier,
        "rating": row.rating,
        "wins": row.wins,
        "losses": row.losses,
        "is_me": row.user_id == user.id,
        "profile_url": reverse("world_profile", args=[row.user.username]),
    }


@login_required(login_url="/login/")
def world_home(request):
    if not _student_only(request):
        return redirect("student_dashboard_root")
    subject = request.GET.get("subject") or WorldRating.SUBJECT_MATH
    if subject not in {WorldRating.SUBJECT_MATH, WorldRating.SUBJECT_RW}:
        subject = WorldRating.SUBJECT_MATH
    context = _world_context(request.user, subject=subject)
    active_match = (
        WorldMatch.objects.filter(status__in=[WorldMatch.STATUS_WAITING, WorldMatch.STATUS_ACTIVE])
        .filter(Q(player1=request.user) | Q(player2=request.user))
        .order_by("-created_at")
        .first()
    )
    if active_match and active_match.status == WorldMatch.STATUS_WAITING and expire_waiting_match(active_match):
        active_match = None
    context.update({
        "world_active": "play",
        "world_initial_mode": "duel",
        "world_active_match": active_match,
        "world_multiplayer_room": multiplayer_room_for_user(request.user),
        "world_recent_matches": list(
            WorldMatch.objects.filter(status=WorldMatch.STATUS_COMPLETED)
            .filter(Q(player1=request.user) | Q(player2=request.user))
            .order_by("-completed_at")[:4]
        ),
        "world_queue_limit_seconds": QUEUE_MAX_SECONDS,
    })
    return render(request, "world/home.html", context)


@login_required(login_url="/login/")
def world_leaderboard(request):
    if not _student_only(request):
        return redirect("student_dashboard_root")
    subject = request.GET.get("subject") or WorldRating.SUBJECT_MATH
    if subject not in {WorldRating.SUBJECT_MATH, WorldRating.SUBJECT_RW}:
        subject = WorldRating.SUBJECT_MATH
    context = _world_context(request.user, subject=subject)
    rows = leaderboard(subject, limit=100)
    needle = (request.GET.get("q") or "").strip().casefold()
    if needle:
        rows = [
            row for row in rows
            if needle in (row.user.get_full_name() or row.user.username).casefold()
            or needle in row.user.username.casefold()
        ]
    context.update({
        "world_active": "ranks",
        "world_leaderboard_rows": rows,
        "world_query": request.GET.get("q", ""),
    })
    return render(request, "world/leaderboard.html", context)


@login_required(login_url="/login/")
def world_leaderboard_search(request):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    subject = (request.GET.get("subject") or WorldRating.SUBJECT_MATH).strip().lower()
    if subject not in {WorldRating.SUBJECT_MATH, WorldRating.SUBJECT_RW}:
        return JsonResponse({"ok": False, "error": "Invalid subject."}, status=400)
    query = (request.GET.get("q") or "").strip()[:80]
    qs = WorldRating.objects.filter(subject=subject).select_related("user")
    if query:
        qs = qs.filter(
            Q(user__username__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
        )
    rows = list(qs.order_by("-rating", "user_id")[:30])
    return JsonResponse({
        "ok": True,
        "subject": subject,
        "query": query,
        "rows": [_leaderboard_payload(row, user=request.user) for row in rows],
    })


@login_required(login_url="/login/")
@require_POST
def world_queue_join(request):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    subject = (request.POST.get("subject") or "").strip().lower()
    mode = (request.POST.get("mode") or "").strip().lower()
    try:
        match, _created = join_queue(request.user, subject=subject, mode=mode)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except RuntimeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=409)
    return JsonResponse({
        "ok": True,
        "match_id": str(match.id),
        "status": match.status,
        "room_url": reverse("world_match", args=[match.id]),
        "queue_limit_seconds": QUEUE_MAX_SECONDS,
        "queue_seconds_remaining": queue_seconds_remaining(match),
    })


@login_required(login_url="/login/")
@never_cache
def world_queue_status(request, match_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    match = get_object_or_404(WorldMatch.objects.select_related("player1", "player2", "winner"), pk=match_id)
    if not match.includes(request.user) and match.player1_id != request.user.id:
        return JsonResponse({"ok": False, "error": "Match unavailable."}, status=404)
    queue_timed_out = False
    # A second browser can activate the canonical (older) queue row while this
    # tab is still polling a newer/cancelled row. Always recover the user's
    # real active room first so Chrome/Firefox converge immediately.
    replacement = active_match_for_user(request.user)
    if replacement and replacement.pk != match.pk:
        match = replacement
    if match.status == WorldMatch.STATUS_WAITING:
        # Preserve the public queue API contract: an already-expired waiting
        # row must report queue_timed_out=True. Reconciliation also expires
        # stale rows, but that path cannot distinguish a timeout from a normal
        # cancellation once the row has been updated.
        if queue_seconds_remaining(match) <= 0:
            queue_timed_out = expire_waiting_match(match)
            if queue_timed_out:
                match.refresh_from_db()
        else:
            match, matched_now = reconcile_waiting_match(match)
            if match.status == WorldMatch.STATUS_WAITING:
                queue_timed_out = expire_waiting_match(match)
                if queue_timed_out:
                    match.refresh_from_db()
            elif matched_now and match.status == WorldMatch.STATUS_ACTIVE:
                match.refresh_from_db()
    if match.status == WorldMatch.STATUS_CANCELLED and not queue_timed_out:
        replacement = active_match_for_user(request.user)
        if replacement:
            match = replacement
    if match.status == WorldMatch.STATUS_ACTIVE:
        resolve_disconnect_forfeit(match)
        match.refresh_from_db()
    opponent = match.opponent_for(request.user)
    my_answered_count = opponent_answered_count = 0
    question_ready = False
    next_number = None
    if match.status == WorldMatch.STATUS_ACTIVE and match.player2_id:
        p1_count, p2_count = answered_counts(match)
        if match.player1_id == request.user.id:
            my_answered_count, opponent_answered_count = p1_count, p2_count
        else:
            my_answered_count, opponent_answered_count = p2_count, p1_count
        next_index = next_question_index(match, request.user)
        question_ready = next_index is not None
        next_number = (next_index + 1) if next_index is not None else None
    return JsonResponse({
        "ok": True,
        "status": match.status,
        "room_url": reverse("world_match", args=[match.id]),
        "opponent": (opponent.get_full_name() or opponent.username) if opponent else None,
        "opponent_profile_url": reverse("world_profile", args=[opponent.username]) if opponent else None,
        "my_score": match.score_for(request.user),
        "opponent_score": match.score_for(opponent) if opponent else 0,
        "completed": match.status == WorldMatch.STATUS_COMPLETED,
        "queue_timed_out": queue_timed_out,
        "queue_limit_seconds": QUEUE_MAX_SECONDS,
        "queue_seconds_remaining": queue_seconds_remaining(match),
        "my_answered_count": my_answered_count,
        "opponent_answered_count": opponent_answered_count,
        "question_ready": question_ready,
        "next_question_number": next_number,
        "intro_seconds_remaining": match_intro_seconds_remaining(match),
        "total_questions": match.total_questions,
    })


@login_required(login_url="/login/")
@require_POST
def world_queue_cancel(request, match_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    match = get_object_or_404(WorldMatch, pk=match_id)
    if not cancel_waiting_match(match, request.user):
        return JsonResponse({"ok": False, "error": "This queue can no longer be cancelled."}, status=409)
    return JsonResponse({"ok": True})


@login_required(login_url="/login/")
@require_POST
def world_match_heartbeat(request, match_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    match = get_object_or_404(WorldMatch, pk=match_id)
    if not match.includes(request.user):
        return JsonResponse({"ok": False, "error": "Match unavailable."}, status=404)
    match = heartbeat(match, request.user)
    return JsonResponse({"ok": True, "status": match.status})


@login_required(login_url="/login/")
@ensure_csrf_cookie
@never_cache
def world_match(request, match_id):
    if not _student_only(request):
        return redirect("student_dashboard_root")
    match = get_object_or_404(WorldMatch.objects.select_related("player1", "player2", "winner"), pk=match_id)
    if not match.includes(request.user) and match.player1_id != request.user.id:
        raise Http404
    if match.status == WorldMatch.STATUS_ACTIVE:
        match = heartbeat(match, request.user)
    context = _world_context(request.user, subject=match.subject)
    opponent = match.opponent_for(request.user)
    intro_seconds_remaining = match_intro_seconds_remaining(match)
    p1_count = p2_count = 0
    my_answered_count = opponent_answered_count = 0
    if match.status == WorldMatch.STATUS_ACTIVE and match.player2_id:
        p1_count, p2_count = answered_counts(match)
        if match.player1_id == request.user.id:
            my_answered_count, opponent_answered_count = p1_count, p2_count
        else:
            my_answered_count, opponent_answered_count = p2_count, p1_count

    # The intro is a per-client gate, not a wall-clock race. A slow browser
    # must still see MATCH FOUND even if the other client opened the room
    # several seconds earlier. After the countdown JS reloads with
    # ?intro=done, and only then do we issue this player's first ticket.
    intro_done = request.GET.get("intro") == "done"
    show_match_intro = bool(
        match.status == WorldMatch.STATUS_ACTIVE
        and opponent
        and my_answered_count == 0
        and not intro_done
    )

    # Question state can move while this GET is rendering (another tab, the
    # opponent finishing the barrier, or a just-completed answer request).
    # Treat that as normal concurrent gameplay, never as a 500. We retry a
    # fresh snapshot a few times and, if it keeps moving, render the waiting
    # state so the room poll can recover on the next tick.
    question_index = None
    question = None
    pool_entry = None
    ticket = None
    if match.status == WorldMatch.STATUS_ACTIVE and not show_match_intro:
        for _attempt in range(3):
            candidate_index = next_question_index(match, request.user)
            if candidate_index is None:
                break
            candidate_question = get_question(match, candidate_index)
            if candidate_question is None:
                question_index = candidate_index
                break
            try:
                candidate_ticket = issue_question_ticket(match, request.user, candidate_index)
            except ValueError as exc:
                if str(exc) != "Question is no longer current.":
                    raise
                # The state changed between next_question_index() and ticket
                # issuance. Refresh counters/state and try the new current
                # question instead of surfacing an exception to the player.
                match.refresh_from_db()
                continue
            question_index = candidate_index
            question = candidate_question
            pool_entry = get_pool_entry(match, candidate_index)
            ticket = candidate_ticket
            break
    my_score = match.score_for(request.user)
    opponent_score = match.score_for(opponent) if opponent else 0
    rating_before = match.player1_rating_before if match.player1_id == request.user.id else match.player2_rating_before
    rating_after = match.player1_rating_after if match.player1_id == request.user.id else match.player2_rating_after
    remaining_seconds = None
    if ticket:
        remaining_seconds = max(0, int((ticket.deadline_at - timezone.now()).total_seconds()))
    waiting_for_opponent = False
    if match.status == WorldMatch.STATUS_ACTIVE and match.player2_id:
        waiting_for_opponent = (
            not show_match_intro
            and question_index is None
            and my_answered_count < match.total_questions
            and my_answered_count > opponent_answered_count
        )
    opponent_rating = ensure_ratings(opponent)[match.subject] if opponent else None
    context.update({
        "world_active": "play",
        "world_compact_topbar": True,
        "match": match,
        "opponent": opponent,
        "opponent_rating": opponent_rating,
        "opponent_profile_url": reverse("world_profile", args=[opponent.username]) if opponent else None,
        "question_index": question_index,
        "question_number": (question_index + 1) if question_index is not None else None,
        "question": question,
        "pool_entry": pool_entry,
        "question_ticket": ticket,
        "question_seconds": remaining_seconds,
        "my_score": my_score,
        "opponent_score": opponent_score,
        "my_answered_count": my_answered_count,
        "opponent_answered_count": opponent_answered_count,
        "waiting_for_opponent": waiting_for_opponent,
        "intro_seconds_remaining": max(3, intro_seconds_remaining) if show_match_intro else 0,
        "show_match_intro": show_match_intro,
        "rating_delta": rating_after - rating_before,
    })
    return render(request, "world/match.html", context)


@login_required(login_url="/login/")
@require_POST
def world_match_answer(request, match_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    match = get_object_or_404(WorldMatch, pk=match_id)
    if not match.includes(request.user):
        return JsonResponse({"ok": False, "error": "Match unavailable."}, status=404)
    token = (request.POST.get("question_token") or "").strip()
    selected = (request.POST.get("answer") or "").strip().upper()
    if not token:
        return JsonResponse({"ok": False, "error": "Question token is required."}, status=400)
    try:
        answer, locked = submit_answer_by_token(match, request.user, token, selected)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=409)
    my_answered_count = opponent_answered_count = 0
    waiting_for_opponent = False
    if locked.status == WorldMatch.STATUS_ACTIVE and locked.player2_id:
        p1_count, p2_count = answered_counts(locked)
        if locked.player1_id == request.user.id:
            my_answered_count, opponent_answered_count = p1_count, p2_count
        else:
            my_answered_count, opponent_answered_count = p2_count, p1_count
        waiting_for_opponent = my_answered_count < locked.total_questions and my_answered_count > opponent_answered_count
    return JsonResponse({
        "ok": True,
        "correct": answer.is_correct,
        "points": answer.points,
        "integrity": answer.integrity_flag,
        "status": locked.status,
        "redirect_url": reverse("world_match", args=[locked.id]),
        "my_score": locked.score_for(request.user),
        "my_answered_count": my_answered_count,
        "opponent_answered_count": opponent_answered_count,
        "waiting_for_opponent": waiting_for_opponent,
        "total_questions": locked.total_questions,
    })


@login_required(login_url="/login/")
@require_POST
def world_rematch_request(request, match_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    source = get_object_or_404(WorldMatch.objects.select_related("player1", "player2"), pk=match_id)
    try:
        invite, created = create_rematch_invite(source, request.user)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=409)
    opponent = source.opponent_for(request.user)
    if created and invite.status == WorldMatch.STATUS_WAITING:
        MakonNotification.objects.create(
            user=opponent,
            type=MakonNotification.TYPE_CLASSROOM,
            title=f"Rematch challenge from {request.user.get_full_name() or request.user.username}",
            message=f"{source.get_subject_display()} · {source.get_mode_display()}. Accept or decline the rematch.",
            url=reverse("world_rematch_offer", args=[invite.id]),
        )
    activated = invite.status == WorldMatch.STATUS_ACTIVE
    return JsonResponse({
        "ok": True,
        "created": created,
        "activated": activated,
        "invite_id": str(invite.id),
        "status_url": reverse("world_queue_status", args=[invite.id]),
        "cancel_url": reverse("world_rematch_cancel", args=[invite.id]),
        "room_url": reverse("world_match", args=[invite.id]) if activated else None,
        "seconds_remaining": queue_seconds_remaining(invite),
        "message": (
            "Rematch accepted. Starting…" if activated
            else "Rematch requested." if created
            else "Rematch request is already pending."
        ),
    })


@login_required(login_url="/login/")
@never_cache
def world_rematch_incoming(request):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    invite = incoming_rematch_invite(request.user)
    if not invite:
        return JsonResponse({"ok": True, "invite": None})
    requester = invite.player1
    rating = ensure_ratings(requester)[invite.subject]
    display = requester.get_full_name() or requester.username
    initials = "".join(part[:1] for part in display.split()[:2]).upper() or requester.username[:1].upper()
    return JsonResponse({
        "ok": True,
        "invite": {
            "id": str(invite.id),
            "requester": display,
            "username": requester.username,
            "initials": initials,
            "rating": rating.rating,
            "tier": rating.tier,
            "subject": invite.get_subject_display(),
            "mode": invite.get_mode_display(),
            "seconds_remaining": queue_seconds_remaining(invite),
            "accept_url": reverse("world_rematch_accept", args=[invite.id]),
            "decline_url": reverse("world_rematch_decline", args=[invite.id]),
            "profile_url": reverse("world_profile", args=[requester.username]),
        },
    })


@login_required(login_url="/login/")
@require_POST
def world_rematch_cancel(request, match_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    invite = get_object_or_404(WorldMatch, pk=match_id)
    if invite.player1_id != request.user.id or not invite.invitee_id or not invite.rematch_of_id:
        return JsonResponse({"ok": False, "error": "Rematch challenge unavailable."}, status=404)
    if not cancel_waiting_match(invite, request.user):
        return JsonResponse({"ok": False, "error": "This rematch challenge can no longer be cancelled."}, status=409)
    MakonNotification.objects.filter(
        user=invite.invitee,
        url=reverse("world_rematch_offer", args=[invite.id]),
        is_read=False,
    ).update(is_read=True)
    return JsonResponse({"ok": True, "status": invite.status})


@login_required(login_url="/login/")
def world_rematch_offer(request, match_id):
    if not _student_only(request):
        return redirect("student_dashboard_root")
    invite = get_object_or_404(WorldMatch.objects.select_related("player1", "invitee", "rematch_of"), pk=match_id)
    if invite.invitee_id != request.user.id:
        raise Http404
    context = _world_context(request.user, subject=invite.subject)
    context.update({
        "world_active": "play",
        "world_compact_topbar": True,
        "rematch_invite": invite,
        "rematch_requester": invite.player1,
        "rematch_expired": invite.status != WorldMatch.STATUS_WAITING or queue_seconds_remaining(invite) <= 0,
    })
    return render(request, "world/rematch_offer.html", context)


@login_required(login_url="/login/")
@require_POST
def world_rematch_accept(request, match_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    invite = get_object_or_404(WorldMatch, pk=match_id)
    try:
        match = accept_rematch_invite(invite, request.user)
    except (ValueError, RuntimeError) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=409)
    MakonNotification.objects.filter(user=request.user, url=reverse("world_rematch_offer", args=[invite.id]), is_read=False).update(is_read=True)
    return JsonResponse({"ok": True, "room_url": reverse("world_match", args=[match.id])})


@login_required(login_url="/login/")
@require_POST
def world_rematch_decline(request, match_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    invite = get_object_or_404(WorldMatch, pk=match_id)
    if not decline_rematch_invite(invite, request.user):
        return JsonResponse({"ok": False, "error": "This rematch invite is no longer available."}, status=409)
    MakonNotification.objects.filter(user=request.user, url=reverse("world_rematch_offer", args=[invite.id]), is_read=False).update(is_read=True)
    return JsonResponse({"ok": True, "redirect_url": reverse("world_home")})


@login_required(login_url="/login/")
def world_profile(request, username):
    if not _student_only(request):
        return redirect("student_dashboard_root")
    profile_user = get_object_or_404(User, username=username)
    subject = request.GET.get("subject") or WorldRating.SUBJECT_MATH
    if subject not in {WorldRating.SUBJECT_MATH, WorldRating.SUBJECT_RW}:
        subject = WorldRating.SUBJECT_MATH
    context = _world_context(request.user, subject=subject)
    ratings = ensure_ratings(profile_user)
    profile_state = GamificationProfile.objects.filter(user=profile_user).first()
    xp_snapshot = level_snapshot(profile_state.xp_total) if profile_state else level_snapshot(0)
    achievements = list(UserAchievement.objects.filter(user=profile_user).order_by("-unlocked_at", "-id")[:12])
    recent_matches = list(
        WorldMatch.objects.filter(status=WorldMatch.STATUS_COMPLETED)
        .filter(Q(player1=profile_user) | Q(player2=profile_user))
        .select_related("player1", "player2", "winner")
        .order_by("-completed_at")[:8]
    )
    total_completed = sum(rating.draws + rating.wins + rating.losses for rating in ratings.values())
    context.update({
        "world_active": "ranks",
        "world_profile_user": profile_user,
        "world_profile_math_rating": ratings[WorldRating.SUBJECT_MATH],
        "world_profile_rw_rating": ratings[WorldRating.SUBJECT_RW],
        "world_profile_xp": xp_snapshot,
        "world_profile_streak": profile_state.current_streak if profile_state else 0,
        "world_profile_best_streak": profile_state.best_streak if profile_state else 0,
        "world_profile_achievements": achievements,
        "world_profile_recent_matches": recent_matches,
        "world_profile_total_completed": total_completed,
        "world_profile_is_me": profile_user.id == request.user.id,
    })
    return render(request, "world/profile.html", context)


@login_required(login_url="/login/")
def world_multiplayer_home(request):
    if not _student_only(request):
        return redirect("student_dashboard_root")
    subject = request.GET.get("subject") or WorldRating.SUBJECT_MATH
    if subject not in {WorldRating.SUBJECT_MATH, WorldRating.SUBJECT_RW}:
        subject = WorldRating.SUBJECT_MATH
    context = _world_context(request.user, subject=subject)
    active_match = (
        WorldMatch.objects.filter(status__in=[WorldMatch.STATUS_WAITING, WorldMatch.STATUS_ACTIVE])
        .filter(Q(player1=request.user) | Q(player2=request.user))
        .order_by("-created_at")
        .first()
    )
    if active_match and active_match.status == WorldMatch.STATUS_WAITING and expire_waiting_match(active_match):
        active_match = None
    multiplayer_room = multiplayer_room_for_user(request.user)
    leaving_room_id = (request.GET.get("leaving") or "").strip()
    if multiplayer_room and leaving_room_id and str(multiplayer_room.id) == leaving_room_id:
        # V50.4.16: the Leave action uses a keepalive POST and redirects
        # immediately. Suppress the just-left room on the destination page while
        # that tiny POST finishes on slower/remote databases.
        multiplayer_room = None
    context.update({
        "world_active": "play",
        "world_initial_mode": "multiplayer",
        "world_active_match": active_match,
        "world_multiplayer_room": multiplayer_room,
        "world_recent_matches": list(
            WorldMatch.objects.filter(status=WorldMatch.STATUS_COMPLETED)
            .filter(Q(player1=request.user) | Q(player2=request.user))
            .order_by("-completed_at")[:4]
        ),
        "world_queue_limit_seconds": QUEUE_MAX_SECONDS,
    })
    return render(request, "world/home.html", context)


@login_required(login_url="/login/")
@require_POST
def world_multiplayer_create(request):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    subject = (request.POST.get("subject") or "").strip().lower()
    capacity = request.POST.get("capacity") or 4
    access_type = (request.POST.get("access_type") or WorldMultiplayerRoom.ACCESS_PRIVATE).strip().lower()
    try:
        room = create_multiplayer_room(
            request.user,
            subject=subject,
            capacity=capacity,
            question_count=request.POST.get("question_count", 5),
            access_type=access_type,
            game_mode=request.POST.get("game_mode") or WorldMultiplayerRoom.GAME_MODE_FFA,
        )
    except (ValueError, RuntimeError) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({
        "ok": True,
        "room_id": str(room.id),
        "room_url": reverse("world_multiplayer_room", args=[room.id]),
        "join_code": room.join_code,
    })


@login_required(login_url="/login/")
@require_POST
def world_multiplayer_public_join(request):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Students only"}, status=403)
    subject = request.POST.get("subject") or WorldRating.SUBJECT_MATH
    try:
        capacity = int(request.POST.get("capacity") or 4)
    except (TypeError, ValueError):
        capacity = 4
    try:
        question_count = int(request.POST.get("question_count") or 5)
    except (TypeError, ValueError):
        question_count = 5
    try:
        room, _seat, created = join_public_multiplayer_room(
            request.user,
            subject=subject,
            capacity=capacity,
            question_count=question_count,
            game_mode=request.POST.get("game_mode") or WorldMultiplayerRoom.GAME_MODE_FFA,
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({
        "ok": True,
        "room_id": str(room.id),
        "room_url": reverse("world_multiplayer_room", args=[room.id]),
        "join_code": room.join_code,
        "created_room": created,
    })


@login_required(login_url="/login/")
@require_POST
def world_multiplayer_join(request):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    try:
        room, _seat, created = join_multiplayer_room(request.user, join_code=request.POST.get("join_code"))
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({
        "ok": True,
        "created": created,
        "room_id": str(room.id),
        "room_url": reverse("world_multiplayer_room", args=[room.id]),
        "join_code": room.join_code,
    })


@login_required(login_url="/login/")
@never_cache
def world_multiplayer_room(request, room_id):
    if not _student_only(request):
        return redirect("student_dashboard_root")
    room = get_object_or_404(WorldMultiplayerRoom.objects.select_related("host"), pk=room_id)
    if not room.includes(request.user):
        raise Http404
    payload = multiplayer_room_payload(room, viewer=request.user)
    context = _world_context(request.user, subject=room.subject)
    context.update({
        "world_active": "multiplayer",
        "world_multiplayer_room": room,
        "world_multiplayer_payload": payload,
        "world_multiplayer_seats": payload["seats"],
        "world_multiplayer_invite_url": request.build_absolute_uri(reverse("world_multiplayer_invite", args=[room.join_code])),
        "world_compact_topbar": True,
    })
    return render(request, "world/multiplayer_room.html", context)


@login_required(login_url="/login/")
@never_cache
def world_multiplayer_invite(request, join_code):
    if not _student_only(request):
        return redirect("student_dashboard_root")
    try:
        room, _seat, _created = join_multiplayer_room(request.user, join_code=join_code)
    except ValueError as exc:
        context = _world_context(request.user)
        context.update({"world_active": "multiplayer", "world_multiplayer_invite_error": str(exc)})
        return render(request, "world/multiplayer_invite_error.html", context, status=400)
    return redirect("world_multiplayer_room", room_id=room.id)


@login_required(login_url="/login/")
@require_POST
def world_multiplayer_access(request, room_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    room = get_object_or_404(WorldMultiplayerRoom, pk=room_id)
    if not room.includes(request.user):
        raise Http404
    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or not request.headers.get("Accept")
        or "application/json" in request.headers.get("Accept", "")
    )
    try:
        room = set_multiplayer_access_type(room, request.user, request.POST.get("access_type"))
    except ValueError as exc:
        if wants_json:
            return JsonResponse({"ok": False, "error": str(exc)}, status=409)
        return redirect("world_multiplayer_room", room_id=room.id)
    if not wants_json:
        return redirect("world_multiplayer_room", room_id=room.id)
    payload = multiplayer_room_payload(room, viewer=request.user)
    payload.update({
        "ok": True,
        "message": "Room is now public and visible in matchmaking." if room.access_type == WorldMultiplayerRoom.ACCESS_PUBLIC else "Room is now private. Only the code or invite link can be used to join.",
    })
    return JsonResponse(payload)


@login_required(login_url="/login/")
@require_POST
def world_multiplayer_kick(request, room_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    room = get_object_or_404(WorldMultiplayerRoom, pk=room_id)
    if not room.includes(request.user):
        raise Http404
    try:
        kick_multiplayer_participant(room, request.user, request.POST.get("user_id"))
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    room.refresh_from_db()
    payload = multiplayer_room_payload(room, viewer=request.user)
    payload.update({"ok": True})
    return JsonResponse(payload)


@login_required(login_url="/login/")
@require_POST
def world_multiplayer_swap_request(request, room_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    room = get_object_or_404(WorldMultiplayerRoom, pk=room_id)
    if not room.includes(request.user):
        raise Http404
    try:
        swap = request_multiplayer_seat_swap(room, request.user, request.POST.get("target_user_id"))
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=409)
    room.refresh_from_db()
    payload = multiplayer_room_payload(room, viewer=request.user)
    payload.update({"ok": True, "swap_request_id": str(swap.id)})
    return JsonResponse(payload)


@login_required(login_url="/login/")
@require_POST
def world_multiplayer_swap_respond(request, room_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    room = get_object_or_404(WorldMultiplayerRoom, pk=room_id)
    if not room.includes(request.user):
        raise Http404
    action = (request.POST.get("action") or "decline").strip().lower()
    if action not in {"accept", "decline"}:
        return JsonResponse({"ok": False, "error": "Invalid seat request action."}, status=400)
    try:
        respond_multiplayer_seat_swap(
            room,
            request.user,
            request.POST.get("request_id"),
            accept=action == "accept",
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=409)
    room.refresh_from_db()
    payload = multiplayer_room_payload(room, viewer=request.user)
    payload.update({"ok": True})
    return JsonResponse(payload)


@login_required(login_url="/login/")
@require_POST
def world_multiplayer_swap_cancel(request, room_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    room = get_object_or_404(WorldMultiplayerRoom, pk=room_id)
    if not room.includes(request.user):
        raise Http404
    try:
        cancel_multiplayer_seat_swap(room, request.user, request.POST.get("request_id"))
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=409)
    room.refresh_from_db()
    payload = multiplayer_room_payload(room, viewer=request.user)
    payload.update({"ok": True})
    return JsonResponse(payload)


@login_required(login_url="/login/")
@never_cache
def world_multiplayer_status(request, room_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    room = get_object_or_404(WorldMultiplayerRoom.objects.select_related("host"), pk=room_id)
    if not room.includes(request.user):
        former_seat = (
            WorldMultiplayerSeat.objects.filter(room=room, user=request.user)
            .order_by("-joined_at")
            .first()
        )
        if former_seat and not former_seat.is_active:
            redirect_url = reverse("world_multiplayer_home") + "?notice=disconnected"
            return JsonResponse({
                "ok": True,
                "removed": True,
                "reason": "disconnected",
                "message": "Your reconnect window expired, so the battle continued without this seat.",
                "redirect_url": redirect_url,
            })
        # A seated player's lobby keeps polling this endpoint. If the host removes
        # that seat, tell that browser explicitly so it can leave the stale lobby
        # immediately instead of silently swallowing a 404 forever.
        redirect_url = reverse("world_multiplayer_home") + "?notice=kicked"
        return JsonResponse({
            "ok": True,
            "removed": True,
            "reason": "kicked",
            "message": "You were removed from the room by the host.",
            "redirect_url": redirect_url,
        })
    if room.status == WorldMultiplayerRoom.STATUS_LOBBY:
        # Lobby polling is intentionally lightweight. The previous implementation
        # ran the full play/timer pipeline on every 500 ms status request, which
        # amplified multi-tab traffic and made Ready/Start feel delayed.
        payload = multiplayer_room_payload(room, viewer=request.user)
    else:
        payload = multiplayer_play_payload(room, viewer=request.user, include_question=False)
    payload.update({"ok": True, "room_url": reverse("world_multiplayer_room", args=[room.id]), "play_url": reverse("world_multiplayer_play", args=[room.id])})
    return JsonResponse(payload)


@login_required(login_url="/login/")
@require_POST
def world_multiplayer_heartbeat(request, room_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    room = get_object_or_404(WorldMultiplayerRoom, pk=room_id)
    arena_ready = str(request.POST.get("arena") or "").strip().lower() in {"1", "true", "yes", "on"}
    try:
        room, seat = touch_multiplayer_presence(room, request.user, arena_ready=arena_ready)
    except ValueError as exc:
        return JsonResponse({
            "ok": False,
            "removed": True,
            "error": str(exc),
            "redirect_url": reverse("world_multiplayer_home") + "?notice=disconnected",
        }, status=409)
    return JsonResponse({
        "ok": True,
        "state_version": int(room.state_version or 0),
        "connected": seat.is_connected,
    })


@login_required(login_url="/login/")
@require_POST
def world_multiplayer_ready(request, room_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    room = get_object_or_404(WorldMultiplayerRoom, pk=room_id)
    ready = str(request.POST.get("ready") or "1").strip().lower() not in {"0", "false", "no", "off"}
    try:
        seat = set_multiplayer_ready(room, request.user, ready)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=409)
    room.refresh_from_db()
    payload = multiplayer_room_payload(room, viewer=request.user)
    payload.update({"ok": True, "my_ready": seat.is_ready})
    return JsonResponse(payload)


@login_required(login_url="/login/")
@require_POST
def world_multiplayer_start(request, room_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    room = get_object_or_404(WorldMultiplayerRoom, pk=room_id)
    try:
        room = start_multiplayer_room(room, request.user)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=409)
    except RuntimeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)
    payload = multiplayer_room_payload(room, viewer=request.user)
    payload.update({"ok": True, "play_url": reverse("world_multiplayer_play", args=[room.id])})
    return JsonResponse(payload)


@login_required(login_url="/login/")
@require_POST
def world_multiplayer_leave(request, room_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    room = get_object_or_404(WorldMultiplayerRoom, pk=room_id)
    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or not request.headers.get("Accept")
        or "application/json" in request.headers.get("Accept", "")
    )
    try:
        leave_multiplayer_room(room, request.user)
    except ValueError as exc:
        if wants_json:
            return JsonResponse({"ok": False, "error": str(exc)}, status=409)
        return redirect("world_multiplayer_home")
    if not wants_json:
        return redirect("world_multiplayer_home")
    return JsonResponse({"ok": True, "redirect_url": reverse("world_multiplayer_home")})


@login_required(login_url="/login/")
@never_cache
def world_multiplayer_play(request, room_id):
    if not _student_only(request):
        return redirect("student_dashboard_root")
    room = get_object_or_404(WorldMultiplayerRoom.objects.select_related("host"), pk=room_id)
    if not room.includes(request.user):
        former_seat = WorldMultiplayerSeat.objects.filter(room=room, user=request.user).first()
        if former_seat and not former_seat.is_active:
            return redirect(reverse("world_multiplayer_home") + "?notice=disconnected")
        raise Http404
    if room.status == WorldMultiplayerRoom.STATUS_LOBBY:
        return redirect("world_multiplayer_room", room_id=room.id)
    payload = multiplayer_play_payload(room, viewer=request.user, include_question=True)
    room.refresh_from_db()
    question = payload.get("question")
    context = _world_context(request.user, subject=room.subject)
    context.update({
        "world_active": "multiplayer",
        "world_compact_topbar": True,
        "world_multiplayer_room": room,
        "world_multiplayer_payload": payload,
        "world_multiplayer_seats": payload["seats"],
        "world_multiplayer_ranked_seats": sorted([seat for seat in payload["seats"] if seat.get("occupied")], key=lambda seat: (-seat.get("score", 0), seat.get("seat_number", 99))),
        "world_multiplayer_question": question,
    })
    return render(request, "world/multiplayer_play.html", context)


@login_required(login_url="/login/")
@require_POST
def world_multiplayer_answer(request, room_id):
    if not _student_only(request):
        return JsonResponse({"ok": False, "error": "Student account required."}, status=403)
    room = get_object_or_404(WorldMultiplayerRoom, pk=room_id)
    try:
        answer, updated, advanced = submit_multiplayer_answer(
            room,
            request.user,
            request.POST.get("question_token") or "",
            request.POST.get("answer") or "",
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=409)
    payload = multiplayer_play_payload(updated, viewer=request.user, include_question=False)
    payload.update({
        "ok": True,
        "correct": answer.is_correct,
        "points": answer.points,
        "advanced": advanced,
        "play_url": reverse("world_multiplayer_play", args=[updated.id]),
    })
    return JsonResponse(payload)

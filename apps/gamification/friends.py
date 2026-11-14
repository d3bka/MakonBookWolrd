"""V50.7 Friends: requests, friend list, classmates suggestions.

Students find each other only by a short friend code they choose to share or
among their own classmates — there is no public search over all accounts.
Friends can visit each other's MakonRoom and, when World is open, challenge
each other to a duel.
"""
import secrets

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.sat.models import ClassroomMembership
from apps.sat.student_workspace import should_use_student_workspace

from .models import Friendship, GamificationProfile, UserAchievement
from .services import ensure_gamification_profile, level_snapshot

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
MAX_PENDING_OUTGOING = 30


class FriendError(ValueError):
    """A friend action the user can fix (shown to them as-is)."""


def normalize_code(raw):
    return "".join(ch for ch in (raw or "").upper() if ch in CODE_ALPHABET)


def friend_code_for(user):
    profile = ensure_gamification_profile(user)
    if profile.friend_code:
        return profile.friend_code
    for _ in range(12):
        body = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        code = f"{body[:4]}-{body[4:]}"
        try:
            with transaction.atomic():
                updated = GamificationProfile.objects.filter(pk=profile.pk, friend_code__isnull=True).update(friend_code=code)
        except IntegrityError:
            continue  # astronomically rare collision: try another code
        if updated:
            return code
        profile.refresh_from_db(fields=["friend_code"])
        return profile.friend_code
    raise RuntimeError("Could not allocate a friend code.")


def user_by_code(raw):
    body = normalize_code(raw)
    if len(body) != 8:
        return None
    profile = GamificationProfile.objects.select_related("user").filter(friend_code=f"{body[:4]}-{body[4:]}").first()
    return profile.user if profile else None


def _pair(a, b):
    return Friendship.objects.filter(Q(from_user=a, to_user=b) | Q(from_user=b, to_user=a))


def are_friends(a, b):
    if not a or not b or a.pk == b.pk:
        return False
    return _pair(a, b).filter(status=Friendship.STATUS_ACCEPTED).exists()


def friends_of(user):
    rows = Friendship.objects.filter(Q(from_user=user) | Q(to_user=user), status=Friendship.STATUS_ACCEPTED)
    ids = {row.to_user_id if row.from_user_id == user.id else row.from_user_id for row in rows}
    return User.objects.filter(pk__in=ids).order_by("first_name", "username")


def incoming_requests(user):
    return Friendship.objects.filter(to_user=user, status=Friendship.STATUS_PENDING).select_related("from_user").order_by("-created_at")


def outgoing_requests(user):
    return Friendship.objects.filter(from_user=user, status=Friendship.STATUS_PENDING).select_related("to_user").order_by("-created_at")


def pending_count(user):
    return Friendship.objects.filter(to_user=user, status=Friendship.STATUS_PENDING).count()


def send_request(user, target):
    """Send a request (or accept theirs). Returns (friendship, accepted_now)."""
    if target is None:
        raise FriendError("No student has that friend code.")
    if target.pk == user.pk:
        raise FriendError("That's your own code — share it with a friend instead.")
    if not should_use_student_workspace(target):
        raise FriendError("Friends are for student accounts.")
    existing = _pair(user, target).first()
    if existing:
        if existing.status == Friendship.STATUS_ACCEPTED:
            raise FriendError(f"You're already friends with {display_name(target)}.")
        if existing.from_user_id == user.pk:
            raise FriendError(f"Your request to {display_name(target)} is still waiting.")
        return respond(user, existing.pk, accept=True), True  # they asked first: that's a yes
    if Friendship.objects.filter(from_user=user, status=Friendship.STATUS_PENDING).count() >= MAX_PENDING_OUTGOING:
        raise FriendError("You have too many requests waiting. Cancel a few first.")
    try:
        return Friendship.objects.create(from_user=user, to_user=target), False
    except IntegrityError:  # a double click raced the first request
        return _pair(user, target).first(), False


def respond(user, request_id, *, accept):
    row = Friendship.objects.filter(pk=request_id, to_user=user, status=Friendship.STATUS_PENDING).first()
    if not row:
        raise FriendError("That request is no longer available.")
    if accept:
        row.status = Friendship.STATUS_ACCEPTED
        row.responded_at = timezone.now()
        row.save(update_fields=["status", "responded_at"])
        return row
    row.delete()
    return None


def cancel(user, request_id):
    return Friendship.objects.filter(pk=request_id, from_user=user, status=Friendship.STATUS_PENDING).delete()[0] > 0


def remove(user, friend):
    return _pair(user, friend).filter(status=Friendship.STATUS_ACCEPTED).delete()[0] > 0


def classmate_suggestions(user, limit=8):
    classrooms = ClassroomMembership.objects.filter(user=user, role="student", status="approved").values("classroom_id")
    related = set(Friendship.objects.filter(Q(from_user=user) | Q(to_user=user)).values_list("from_user_id", "to_user_id"))
    taken = {uid for pair in related for uid in pair} | {user.pk}
    mates = (
        User.objects.filter(classroom_memberships__classroom_id__in=classrooms,
                            classroom_memberships__role="student", classroom_memberships__status="approved",
                            is_active=True)
        .exclude(pk__in=taken).distinct().order_by("first_name", "username")
    )
    return [u for u in mates[: limit * 2] if should_use_student_workspace(u)][:limit]


def display_name(user):
    return user.get_full_name().strip() or user.username


def initials(user):
    name = display_name(user)
    return "".join(part[:1] for part in name.split()[:2]).upper() or user.username[:1].upper()


def friend_card(user):
    profile = GamificationProfile.objects.filter(user=user).first()
    xp = profile.xp_total if profile else 0
    return {
        "user": user,
        "username": user.username,
        "name": display_name(user),
        "initials": initials(user),
        "level": level_snapshot(xp)["level"],
        "streak": profile.current_streak if profile else 0,
        "trophies": UserAchievement.objects.filter(user=user).count(),
    }

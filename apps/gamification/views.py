"""V50.6 MakonRoom pages."""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.base.seasons import current_season
from apps.sat.student_workspace import should_use_student_workspace, student_workspace_context

from . import room


@login_required
@require_GET
def makon_room(request):
    if not should_use_student_workspace(request.user):
        return redirect("student_dashboard_root")
    context = student_workspace_context(request.user, active="room", enabled=True)
    context.update(room.room_context(request.user))
    context["room_season"] = current_season().key
    return render(request, "gamification/room.html", context)


@login_required
@require_POST
def makon_room_equip(request):
    if not should_use_student_workspace(request.user):
        return JsonResponse({"ok": False, "error": "Students only."}, status=403)
    slot = (request.POST.get("slot") or "").strip()
    code = (request.POST.get("item") or "").strip()
    try:
        equipped = room.equip(request.user, slot, code)
    except PermissionError as locked:
        return JsonResponse({"ok": False, "error": f"Locked — {locked}"}, status=403)
    except ValueError as bad:
        return JsonResponse({"ok": False, "error": str(bad)}, status=400)
    return JsonResponse({"ok": True, "equipped": equipped})


# ---------------------------------------------------------------- V50.7 friends
from django.conf import settings  # noqa: E402
from django.contrib import messages  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.http import Http404  # noqa: E402
from django.shortcuts import get_object_or_404  # noqa: E402
from django.urls import reverse  # noqa: E402

from apps.sat.models import MakonNotification  # noqa: E402

from . import friends as social  # noqa: E402


def _students_only(view):
    def wrapped(request, *args, **kwargs):
        if not should_use_student_workspace(request.user):
            return redirect("student_dashboard_root")
        return view(request, *args, **kwargs)
    wrapped.__name__ = view.__name__
    return wrapped


def _notify(user, title, message=""):
    MakonNotification.objects.create(user=user, type=MakonNotification.TYPE_SOCIAL, title=title,
                                     message=message, url=reverse("friends"))


@login_required
@require_GET
@_students_only
def friends_page(request):
    user = request.user
    context = student_workspace_context(user, active="friends", enabled=True)
    context.update({
        "friend_code": social.friend_code_for(user),
        "friend_cards": [social.friend_card(f) for f in social.friends_of(user)],
        "friend_incoming": [{"id": r.pk, **social.friend_card(r.from_user)} for r in social.incoming_requests(user)],
        "friend_outgoing": [{"id": r.pk, **social.friend_card(r.to_user)} for r in social.outgoing_requests(user)],
        "friend_suggestions": [social.friend_card(u) for u in social.classmate_suggestions(user)],
        "world_enabled": getattr(settings, "MAKONBOOK_WORLD_ENABLED", False),
    })
    return render(request, "gamification/friends.html", context)


@login_required
@require_POST
@_students_only
def friends_add(request):
    user = request.user
    suggested = request.POST.get("suggest")
    if suggested:
        target = next((u for u in social.classmate_suggestions(user, limit=50) if str(u.pk) == suggested), None)
        if target is None:
            messages.error(request, "That classmate is no longer available.")
            return redirect("friends")
    else:
        target = social.user_by_code(request.POST.get("code"))
    try:
        row, accepted = social.send_request(user, target)
    except social.FriendError as exc:
        messages.error(request, str(exc))
        return redirect("friends")
    name = social.display_name(target)
    if accepted:
        _notify(target, f"{social.display_name(user)} accepted your friend request")
        messages.success(request, f"You and {name} are friends now.")
    else:
        _notify(target, f"{social.display_name(user)} sent you a friend request", "Accept it on your Friends page.")
        messages.success(request, f"Request sent to {name}.")
    return redirect("friends")


@login_required
@require_POST
@_students_only
def friends_respond(request, request_id, action):
    if action not in ("accept", "decline"):
        raise Http404
    try:
        row = social.respond(request.user, request_id, accept=(action == "accept"))
    except social.FriendError as exc:
        messages.error(request, str(exc))
        return redirect("friends")
    if row:
        _notify(row.from_user, f"{social.display_name(request.user)} accepted your friend request")
        messages.success(request, f"You and {social.display_name(row.from_user)} are friends now.")
    else:
        messages.info(request, "Request declined.")
    return redirect("friends")


@login_required
@require_POST
@_students_only
def friends_cancel(request, request_id):
    if social.cancel(request.user, request_id):
        messages.info(request, "Request cancelled.")
    return redirect("friends")


@login_required
@require_POST
@_students_only
def friends_remove(request, username):
    friend = get_object_or_404(User, username=username)
    if social.remove(request.user, friend):
        messages.info(request, f"{social.display_name(friend)} was removed from your friends.")
    return redirect("friends")


@login_required
@require_GET
@_students_only
def friend_room(request, username):
    friend = get_object_or_404(User, username=username)
    if friend.pk == request.user.pk:
        return redirect("makon_room")
    if not social.are_friends(request.user, friend):
        raise Http404("Rooms are visible to friends only.")
    context = student_workspace_context(request.user, active="friends", enabled=True)
    context.update(room.room_context(friend, mark_seen=False))
    context.update({
        "room_season": current_season().key,
        "room_readonly": True,
        "room_owner": social.friend_card(friend),
        "room_new_items": [],
        "world_enabled": getattr(settings, "MAKONBOOK_WORLD_ENABLED", False),
    })
    return render(request, "gamification/room.html", context)

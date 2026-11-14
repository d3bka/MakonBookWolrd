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

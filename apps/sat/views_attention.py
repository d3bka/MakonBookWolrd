"""V102: "Needs attention" — students who miss homework or lessons, score lower or stopped visiting."""
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .models import Classroom, ClassroomMembership, StudentAttentionSnooze
from .roles import is_manager, is_platform_admin, is_teacher
from .student_attention import INACTIVE_DAYS, SNOOZE_DAYS, WINDOW_DAYS, attention_rows


def _int(value):
    value = (value or "").strip()
    return int(value) if value.isdecimal() else None


def _handle_snooze(request, classrooms, back):
    classroom_id = _int(request.POST.get("classroom"))
    student_id = _int(request.POST.get("student"))
    allowed = {c.pk for c in classrooms}
    if classroom_id not in allowed or not ClassroomMembership.objects.filter(
        classroom_id=classroom_id, user_id=student_id, role="student", status="approved",
    ).exists():
        return HttpResponseForbidden("You can manage only your own classrooms.")
    student = User.objects.get(pk=student_id)
    name = student.get_full_name() or student.username
    if request.POST.get("action") == "unsnooze":
        StudentAttentionSnooze.objects.filter(classroom_id=classroom_id, student_id=student_id).delete()
        messages.success(request, f"{name} is back on the list.")
    else:
        StudentAttentionSnooze.objects.update_or_create(
            classroom_id=classroom_id, student_id=student_id,
            defaults={
                "snoozed_by": request.user,
                "note": (request.POST.get("note") or "").strip()[:200],
                "until": timezone.now() + timedelta(days=SNOOZE_DAYS),
            },
        )
        messages.success(request, f"{name} is hidden for {SNOOZE_DAYS} days.")
    return redirect(back)


def _render(request, classrooms, *, scope, teachers=None):
    selected_classroom = _int(request.GET.get("classroom"))
    selected_teacher = _int(request.GET.get("teacher"))
    shown = [c for c in classrooms if c.is_active]
    if selected_teacher:
        shown = [c for c in shown if c.teacher_id == selected_teacher]
    if selected_classroom:
        shown = [c for c in classrooms if c.pk == selected_classroom] or shown

    query = {k: v for k, v in (("classroom", selected_classroom), ("teacher", selected_teacher)) if v}
    back = reverse(f"{scope}_attention_root") + (f"?{urlencode(query)}" if query else "")
    if request.method == "POST":
        return _handle_snooze(request, classrooms, back)

    rows, snoozed = attention_rows(shown)
    return render(request, "sat/student_attention.html", {
        "scope": scope,
        "rows": rows,
        "snoozed_rows": snoozed,
        "classrooms": sorted(
            [c for c in classrooms if c.is_active or c.pk == selected_classroom],
            key=lambda c: c.name.casefold(),
        ),
        "teachers": teachers or [],
        "selected_classroom": selected_classroom,
        "selected_teacher": selected_teacher,
        "counts": {
            "listed": len(rows),
            "high": sum(1 for r in rows if r["level"] == "high"),
            "snoozed": len(snoozed),
            "classrooms": len(shown),
        },
        "rules": {"window": WINDOW_DAYS, "inactive": INACTIVE_DAYS, "snooze": SNOOZE_DAYS},
    })


@login_required(login_url="/login/")
def teacher_attention(request):
    if not is_teacher(request.user):
        return HttpResponseForbidden("Teacher access required.")
    from .views import _teacher_managed_classrooms

    classrooms = list(_teacher_managed_classrooms(request.user).only("pk", "name", "is_active", "teacher_id"))
    return _render(request, classrooms, scope="teacher")


@login_required(login_url="/login/")
def manager_attention(request):
    if not (is_manager(request.user) or is_platform_admin(request.user)):
        return HttpResponseForbidden("Manager access required.")
    classrooms = list(Classroom.objects.select_related("teacher").only(
        "pk", "name", "is_active", "teacher_id", "teacher__first_name", "teacher__last_name", "teacher__username",
    ))
    teachers = {}
    for classroom in classrooms:
        if classroom.is_active and classroom.teacher_id:
            teachers[classroom.teacher_id] = classroom.teacher.get_full_name() or classroom.teacher.username
    return _render(
        request, classrooms, scope="manager",
        teachers=sorted(teachers.items(), key=lambda item: item[1].casefold()),
    )

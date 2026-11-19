"""V93: the 'no attempts left' page for students and the teacher's attempt requests page."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import attempt_limits
from .attempt_limit_models import SatAttemptRequest
from .models import Test
from .roles import is_manager, is_platform_admin, is_teacher
from .student_workspace import should_use_student_workspace, student_workspace_context


def _can_review(user):
    return is_teacher(user) or is_manager(user) or is_platform_admin(user)


@login_required(login_url="/login/")
def practice_test_attempts(request, pk):
    test = get_object_or_404(Test, name=pk)
    if request.method == "POST":
        try:
            attempt_limits.ask_teacher(request.user, test, request.POST.get("message"))
        except attempt_limits.LimitError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Sent to your teacher. You will get a notification when they decide.")
        return redirect("practice_test_attempts_root", pk=test.name)

    info = attempt_limits.state(request.user, test)
    if not info["exhausted"]:
        return redirect("practice_test_start_root", pk=test.name)
    history = SatAttemptRequest.objects.filter(user=request.user, test=test).select_related("decided_by")[:6]
    context = {
        "test": test,
        "attempts": info,
        "requests_history": history,
        "satmakon_limit": attempt_limits.student_limit(),
        "practice_library_url": reverse("practice_tests_root"),
    }
    if should_use_student_workspace(request.user):
        context.update(student_workspace_context(request.user, active="tests"))
    return render(request, "sat/attempt_limit.html", context)


@login_required(login_url="/login/")
@require_POST
def withdraw_attempt_request(request, request_id):
    row = get_object_or_404(SatAttemptRequest, pk=request_id, user=request.user)
    try:
        attempt_limits.withdraw(request.user, row)
    except attempt_limits.LimitError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Request withdrawn.")
    return redirect("practice_test_attempts_root", pk=row.test.name)


@login_required(login_url="/login/")
def teacher_attempt_requests(request):
    if not _can_review(request.user):
        return HttpResponseForbidden("Teacher access required.")
    if request.method == "POST":
        row = get_object_or_404(SatAttemptRequest, pk=request.POST.get("request_id"))
        decision = request.POST.get("decision")
        if decision not in {"approve", "reject"}:
            messages.error(request, "Choose Approve or Reject.")
            return redirect("teacher_attempt_requests_root")
        try:
            row = attempt_limits.decide(
                request.user, row, approve=decision == "approve",
                granted=request.POST.get("granted"), note=request.POST.get("note"),
            )
        except attempt_limits.LimitError as exc:
            messages.error(request, str(exc))
        else:
            name = row.user.get_full_name() or row.user.username
            if row.status == SatAttemptRequest.APPROVED:
                messages.success(request, f"{name} got {row.granted} more attempt(s) at {row.test.name}.")
            else:
                messages.success(request, f"Request from {name} rejected.")
        return redirect("teacher_attempt_requests_root")

    pending = attempt_limits.pending_for(request.user)
    for row in pending:
        row.attempt_info = attempt_limits.state(row.user, row.test)
    decided = (
        attempt_limits.requests_for(request.user)
        .exclude(status=SatAttemptRequest.PENDING)
        .order_by("-decided_at", "-created_at")[:20]
    )
    return render(request, "sat/teacher_attempt_requests.html", {
        "pending": pending,
        "decided": decided,
        "grant_choices": range(1, attempt_limits.MAX_GRANT + 1),
        "satmakon_limit": attempt_limits.student_limit(),
        "public_limit": attempt_limits.public_limit(),
        "staff_workspace_active": "attempt-requests",
    })

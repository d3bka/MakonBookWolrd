"""V84: public sign-up (email code) and joining a SATMakon account (SMS code)."""
import logging

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.integrations.hollihop.normalization import normalize_email

from .auth_rate_limit import check_auth_rate_limit
from .decorators import unauthenticated_user
from .models import PendingRegistration
from .registration import RegistrationError, confirm_registration, resend_code, start_registration
from .satmakon_link import (
    LinkError, can_link, candidates_for_phone, confirmed_row, join_accounts, send_link_code, verify_link_code,
)

log = logging.getLogger("makonbook.registration")
BACKEND = "apps.base.auth_backends.EmailOrPhoneModelBackend"
SESSION_PENDING = "register_pending_id"


def _limited(request, action, identifier, template, context):
    rate = check_auth_rate_limit(request, action=action, identifier=identifier)
    if rate.allowed:
        return None
    messages.error(request, "Too many attempts. Please wait a little and try again.")
    response = render(request, template, context, status=429)
    response["Retry-After"] = str(rate.retry_after)
    return response


@unauthenticated_user
def register(request):
    values = {"first_name": "", "last_name": "", "email": ""}
    errors = {}
    if request.method == "POST":
        values = {key: (request.POST.get(key) or "").strip() for key in values}
        password = request.POST.get("password") or ""
        values["email"] = normalize_email(values["email"])
        if not values["first_name"]:
            errors["first_name"] = "Enter your first name."
        if not values["last_name"]:
            errors["last_name"] = "Enter your last name."
        if not values["email"]:
            errors["email"] = "Enter your email."
        if not request.POST.get("agree"):
            errors["agree"] = "Please accept the terms to continue."
        try:
            validate_password(password)
        except ValidationError as exc:
            errors["password"] = " ".join(exc.messages)
        if password != (request.POST.get("password2") or ""):
            errors["password2"] = "The passwords do not match."
        context = {"values": values, "errors": errors}
        blocked = _limited(request, "register", values["email"], "base/register.html", context)
        if blocked:
            return blocked
        if not errors:
            try:
                pending = start_registration(first_name=values["first_name"], last_name=values["last_name"],
                                             email=values["email"], password=password)
            except RegistrationError as exc:
                errors["email"] = str(exc)
            except Exception:  # noqa: BLE001 - the mail server may be down
                log.exception("Sign-up email could not be sent")
                errors["email"] = "We could not send the email right now. Please try again in a few minutes."
            else:
                request.session[SESSION_PENDING] = pending.pk
                return redirect("register_verify")
    return render(request, "base/register.html", {"values": values, "errors": errors})


def _pending(request):
    pending_id = request.session.get(SESSION_PENDING)
    if not pending_id:
        return None
    return PendingRegistration.objects.filter(pk=pending_id, completed_at__isnull=True).first()


@unauthenticated_user
def register_verify(request):
    pending = _pending(request)
    if pending is None:
        messages.info(request, "Start your sign-up here.")
        return redirect("register")
    context = {"pending": pending}
    if request.method == "POST":
        blocked = _limited(request, "register_code", pending.email, "base/register_verify.html", context)
        if blocked:
            return blocked
        try:
            user = confirm_registration(pending, request.POST.get("code"))
        except RegistrationError as exc:
            context["error"] = str(exc)
        else:
            request.session.pop(SESSION_PENDING, None)
            login(request, user, backend=BACKEND)
            messages.success(request, "Welcome to MakonBook! Your account is ready.")
            return redirect("satmakon_link")
    return render(request, "base/register_verify.html", context)


@unauthenticated_user
@require_POST
def register_resend(request):
    pending = _pending(request)
    if pending is None:
        return redirect("register")
    blocked = _limited(request, "register", pending.email, "base/register_verify.html", {"pending": pending})
    if blocked:
        return blocked
    try:
        resend_code(pending)
        messages.success(request, f"A new code was sent to {pending.email}.")
    except RegistrationError as exc:
        messages.error(request, str(exc))
    except Exception:  # noqa: BLE001
        log.exception("Sign-up email could not be re-sent")
        messages.error(request, "We could not send the email right now. Please try again in a few minutes.")
    return redirect("register_verify")


# ---------------------------------------------------------------- SATMakon link


def _link_context(request, **extra):
    from apps.sat.student_workspace import student_workspace_context

    context = student_workspace_context(request.user, active="settings")
    context.update(extra)
    return context


@login_required(login_url="/login/")
def satmakon_link(request):
    """Step 1: "I study at SATMakon" -> phone -> SMS code."""
    if not can_link(request.user):
        return redirect("student_dashboard_root")
    context = _link_context(request, step="phone", phone=(request.POST.get("phone") or "").strip())
    if request.method == "POST":
        blocked = _limited(request, "satmakon_link_send", str(request.user.pk), "sat/satmakon_link.html", context)
        if blocked:
            return blocked
        try:
            row, test_code = send_link_code(request.user, context["phone"])
        except LinkError as exc:
            context["error"] = str(exc)
        else:
            context.update(step="code", phone=row.phone, test_code=test_code)
    return render(request, "sat/satmakon_link.html", context)


@login_required(login_url="/login/")
@require_POST
def satmakon_link_verify(request):
    """Step 2: the SMS code. One student on this number -> join; several -> choose."""
    if not can_link(request.user):
        return redirect("student_dashboard_root")
    context = _link_context(request, step="code")
    blocked = _limited(request, "satmakon_link_verify", str(request.user.pk), "sat/satmakon_link.html", context)
    if blocked:
        return blocked
    try:
        row = verify_link_code(request.user, request.POST.get("code"))
    except LinkError as exc:
        context["error"] = str(exc)
        return render(request, "sat/satmakon_link.html", context)
    students = candidates_for_phone(row.phone)
    if len(students) == 1:
        return _join(request, students[0].user_id, row)
    context.update(step="choose", students=[profile.user for profile in students])
    return render(request, "sat/satmakon_link.html", context)


@login_required(login_url="/login/")
@require_POST
def satmakon_link_choose(request):
    """Step 3 (shared family number): pick which SATMakon student you are."""
    if not can_link(request.user):
        return redirect("student_dashboard_root")
    row = confirmed_row(request.user)
    if row is None:
        messages.error(request, "Your code has expired. Send a new one.")
        return redirect("satmakon_link")
    return _join(request, request.POST.get("student") or 0, row)


def _join(request, target_user_id, row):
    try:
        target = join_accounts(request.user, target_user_id, row)
    except (LinkError, ValueError) as exc:
        messages.error(request, str(exc) or "This account could not be linked.")
        return redirect("satmakon_link")
    logout(request)
    login(request, target, backend=BACKEND)
    messages.success(request, "Your SATMakon account is connected: full MakonBook access and your classrooms are open.")
    return redirect("student_dashboard_root")

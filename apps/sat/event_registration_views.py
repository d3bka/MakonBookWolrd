from __future__ import annotations

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.base.auth_rate_limit import check_auth_rate_limit

from .event_registration import (
    EmailValidationError,
    EventRegistrationError,
    event_confirmed_count,
    event_pending_hold_count,
    find_makonbook_student_by_username,
    is_makonbook_student_account,
    verification_email_for_user,
    masked_email,
    registration_for_request,
    registration_window,
    reserve_external,
    reserve_makonbook_student,
    seats_left,
    send_registration_code,
    verify_registration,
)
from .models import EventRegistration, GlobalEvent


def _wants_json(request) -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in (request.headers.get("Accept") or "")


def _email_error_payload(exc: EmailValidationError, *, include_profile_url: bool = False):
    payload = {
        "ok": False,
        "error": str(exc),
        "error_code": exc.code,
        "can_override": bool(exc.can_override),
    }
    if exc.suggested_email:
        payload["suggested_email"] = exc.suggested_email
        payload["masked_suggested_email"] = masked_email(exc.suggested_email)
    if include_profile_url:
        payload["profile_url"] = reverse("edit_profile")
    return payload


def _event(slug):
    return get_object_or_404(
        GlobalEvent.objects.select_related("test"),
        slug=slug,
        registration_enabled=True,
    )


def _is_makonbook_student(user) -> bool:
    return bool(getattr(user, "is_authenticated", False) and is_makonbook_student_account(user))


def _base_context(event, request):
    window = registration_window(event)
    confirmed = registration_for_request(request, event)
    return {
        "event": event,
        "registration_window": window,
        "confirmed_registration": confirmed,
        "confirmed_count": event_confirmed_count(event),
        "pending_hold_count": event_pending_hold_count(event),
        "seats_left": seats_left(event),
        "authenticated_student": _is_makonbook_student(request.user),
        "registration_back_url": reverse("events") if getattr(request.user, "is_authenticated", False) else reverse("home"),
    }


def _confirmed_json_payload(registration, *, confirmation_email_sent=None):
    event = registration.event
    payload = {
        "ok": True,
        "confirmed": True,
        "registration_id": registration.registration_id,
        "confirmation_url": reverse(
            "event_registration_confirmation",
            kwargs={"token": registration.registration_token},
        ),
        "confirmed_count": event_confirmed_count(event),
        "pending_hold_count": event_pending_hold_count(event),
        "seats_left": seats_left(event),
    }
    if confirmation_email_sent is not None:
        payload["confirmation_email_sent"] = bool(confirmation_email_sent)
    return payload




def _pending_json_payload(registration):
    event = registration.event
    return {
        "ok": True,
        "confirmed": False,
        "registration_token": str(registration.registration_token),
        "masked_email": masked_email(registration.email),
        "verify_url": reverse("event_registration_verify", kwargs={"token": registration.registration_token}),
        "resend_url": reverse("event_registration_resend", kwargs={"token": registration.registration_token}),
        "confirmation_url": reverse("event_registration_confirmation", kwargs={"token": registration.registration_token}),
        "confirmed_count": event_confirmed_count(event),
        "pending_hold_count": event_pending_hold_count(event),
        "seats_left": seats_left(event),
    }

def event_registration_choice(request, slug):
    event = _event(slug)
    context = _base_context(event, request)
    if context["confirmed_registration"]:
        return redirect("event_registration_confirmation", token=context["confirmed_registration"].registration_token)
    return render(request, "sat/events/register_choice.html", context)


def event_registration_external(request, slug):
    event = _event(slug)
    context = _base_context(event, request)
    if context["confirmed_registration"]:
        if _wants_json(request):
            return JsonResponse(_confirmed_json_payload(context["confirmed_registration"]))
        return redirect("event_registration_confirmation", token=context["confirmed_registration"].registration_token)

    if request.method == "POST":
        try:
            registration = reserve_external(
                request,
                event,
                full_name=request.POST.get("full_name", ""),
                phone=request.POST.get("phone", ""),
                email=request.POST.get("email", ""),
                telegram=request.POST.get("telegram", ""),
                allow_suspicious_email=request.POST.get("allow_suspicious_email") == "1",
            )
        except EmailValidationError as exc:
            if _wants_json(request):
                return JsonResponse(_email_error_payload(exc), status=409 if exc.can_override else 400)
            if exc.can_override:
                context["email_warning"] = {
                    "message": str(exc),
                    "suggested_email": exc.suggested_email,
                    "masked_suggested_email": masked_email(exc.suggested_email) if exc.suggested_email else "",
                }
            else:
                messages.error(request, str(exc))
        except EventRegistrationError as exc:
            if _wants_json(request):
                return JsonResponse({"ok": False, "error": str(exc)}, status=400)
            messages.error(request, str(exc))
        else:
            request.session[f"pending_event_registration_{event.pk}"] = str(registration.registration_token)
            request.session.modified = True
            if _wants_json(request):
                return JsonResponse(_pending_json_payload(registration))
            return redirect("event_registration_verify", token=registration.registration_token)

    return render(request, "sat/events/register_external.html", context)


def _send_for_authenticated_student(request, event, *, allow_suspicious_email=False):
    if not _is_makonbook_student(request.user):
        raise EventRegistrationError("This MakonBook account is not available for student event registration.")
    registration = reserve_makonbook_student(
        request,
        event,
        request.user,
        allow_suspicious_email=allow_suspicious_email,
    )
    request.session[f"pending_event_registration_{event.pk}"] = str(registration.registration_token)
    request.session.modified = True
    return registration


def event_registration_student(request, slug):
    """Register a SATMakon student for a verified mock event.

    Authenticated workspace flow:
        event info -> Register -> email OTP

    Public landing flow:
        username -> password -> email OTP

    The public flow intentionally does not sign the student in after the password
    step. The email OTP remains the final proof and verify_registration() signs
    the owner into the real MakonBook account only after a valid code.
    """
    event = _event(slug)
    context = _base_context(event, request)
    if context["confirmed_registration"]:
        confirmation_url = reverse(
            "event_registration_confirmation",
            kwargs={"token": context["confirmed_registration"].registration_token},
        )
        if _wants_json(request):
            return JsonResponse(_confirmed_json_payload(context["confirmed_registration"]))
        return redirect("event_registration_confirmation", token=context["confirmed_registration"].registration_token)

    action = request.POST.get("action", "") if request.method == "POST" else ""

    # A student already signed into the MakonBook workspace must never be asked
    # for username/password again. The event card/info dialog POSTs action=send.
    if getattr(request.user, "is_authenticated", False):
        if request.method == "POST" and action in {"send", "register"}:
            try:
                registration = _send_for_authenticated_student(
                    request,
                    event,
                    allow_suspicious_email=request.POST.get("allow_suspicious_email") == "1",
                )
            except EmailValidationError as exc:
                if _wants_json(request):
                    return JsonResponse(
                        _email_error_payload(exc, include_profile_url=True),
                        status=409 if exc.can_override else 400,
                    )
                messages.error(request, str(exc))
                return redirect("events")
            except EventRegistrationError as exc:
                if _wants_json(request):
                    return JsonResponse({"ok": False, "error": str(exc)}, status=400)
                messages.error(request, str(exc))
                return redirect("events")

            confirmation_url = reverse("event_registration_confirmation", kwargs={"token": registration.registration_token})
            if registration.status == EventRegistration.STATUS_CONFIRMED:
                if _wants_json(request):
                    return JsonResponse(_confirmed_json_payload(registration))
                return redirect("event_registration_confirmation", token=registration.registration_token)

            verify_url = reverse("event_registration_verify", kwargs={"token": registration.registration_token})
            if _wants_json(request):
                return JsonResponse(_pending_json_payload(registration))
            return redirect("event_registration_verify", token=registration.registration_token)

        context.update({
            "student_step": "authenticated",
            "matched_student": request.user if _is_makonbook_student(request.user) else None,
            "matched_student_email": masked_email(verification_email_for_user(request.user)) if _is_makonbook_student(request.user) else "",
            "registration_back_url": reverse("events"),
        })
        return render(request, "sat/events/register_student.html", context)

    # Public landing registration always starts with the exact MakonBook
    # username. Email/phone are intentionally not accepted for account discovery.
    username = (request.POST.get("username") or request.POST.get("identifier") or "").strip()
    matched_user = None
    step = "username"

    if request.method == "POST" and action == "lookup":
        matched_user = find_makonbook_student_by_username(username)
        if matched_user is None:
            if _wants_json(request):
                return JsonResponse({"ok": False, "error": "Username or password is incorrect."}, status=400)
            messages.error(request, "Username or password is incorrect.")
        else:
            if _wants_json(request):
                return JsonResponse({
                    "ok": True,
                    "step": "password",
                    "student_user_id": matched_user.pk,
                    "username": matched_user.username,
                    "display_name": matched_user.get_full_name() or matched_user.username,
                    "masked_email": masked_email(verification_email_for_user(matched_user)),
                })
            step = "password"

    elif request.method == "POST" and action == "password":
        posted_user_id = (request.POST.get("student_user_id") or "").strip()
        password = request.POST.get("password") or ""
        matched_user = find_makonbook_student_by_username(username)
        if matched_user is None or str(matched_user.pk) != posted_user_id:
            if _wants_json(request):
                return JsonResponse({"ok": False, "error": "Username or password is incorrect."}, status=400)
            messages.error(request, "Username or password is incorrect.")
            step = "username"
        else:
            rate = check_auth_rate_limit(request, action="login", identifier=username)
            if not rate.allowed:
                if _wants_json(request):
                    return JsonResponse({"ok": False, "error": "Too many sign-in attempts. Please wait before trying again."}, status=429)
                messages.error(request, "Too many sign-in attempts. Please wait before trying again.")
                step = "password"
            elif not matched_user.check_password(password):
                if _wants_json(request):
                    return JsonResponse({"ok": False, "error": "Username or password is incorrect."}, status=400)
                messages.error(request, "Username or password is incorrect.")
                step = "password"
            else:
                try:
                    registration = reserve_makonbook_student(
                        request,
                        event,
                        matched_user,
                        allow_suspicious_email=request.POST.get("allow_suspicious_email") == "1",
                    )
                except EmailValidationError as exc:
                    if _wants_json(request):
                        return JsonResponse(_email_error_payload(exc), status=409 if exc.can_override else 400)
                    if exc.can_override:
                        context["email_warning"] = {
                            "message": str(exc),
                            "suggested_email": exc.suggested_email,
                            "masked_suggested_email": masked_email(exc.suggested_email) if exc.suggested_email else "",
                        }
                    else:
                        messages.error(request, str(exc))
                    step = "password"
                except EventRegistrationError as exc:
                    if _wants_json(request):
                        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
                    messages.error(request, str(exc))
                    step = "password"
                else:
                    if registration.status == EventRegistration.STATUS_CONFIRMED:
                        if _wants_json(request):
                            return JsonResponse(_confirmed_json_payload(registration))
                        return redirect("event_registration_confirmation", token=registration.registration_token)
                    request.session[f"pending_event_registration_{event.pk}"] = str(registration.registration_token)
                    request.session.modified = True
                    if _wants_json(request):
                        return JsonResponse(_pending_json_payload(registration))
                    return redirect("event_registration_verify", token=registration.registration_token)

    context.update({
        "student_step": step,
        "student_username": username,
        "matched_student": matched_user,
        "matched_student_email": masked_email(verification_email_for_user(matched_user)) if matched_user else "",
        "registration_back_url": reverse("event_registration_choice", kwargs={"slug": event.slug}),
    })
    return render(request, "sat/events/register_student.html", context)


def event_registration_verify(request, token):
    registration = get_object_or_404(
        EventRegistration.objects.select_related("event", "user", "guest"),
        registration_token=token,
    )
    event = registration.event
    if registration.status == EventRegistration.STATUS_CONFIRMED:
        confirmation_url = reverse("event_registration_confirmation", kwargs={"token": registration.registration_token})
        if _wants_json(request):
            return JsonResponse(_confirmed_json_payload(registration))
        return redirect("event_registration_confirmation", token=registration.registration_token)

    if request.method == "POST":
        try:
            registration = verify_registration(request, registration, request.POST.get("code", ""))
        except EventRegistrationError as exc:
            if _wants_json(request):
                registration.refresh_from_db(fields=["verification_attempts", "verification_expires_at", "status"])
                return JsonResponse({
                    "ok": False,
                    "error": str(exc),
                    "attempts_left": max(0, 5 - registration.verification_attempts),
                    "expired": registration.status == EventRegistration.STATUS_EXPIRED,
                }, status=400)
            messages.error(request, str(exc))
        else:
            request.session.pop(f"pending_event_registration_{event.pk}", None)
            confirmation_url = reverse("event_registration_confirmation", kwargs={"token": registration.registration_token})
            if _wants_json(request):
                payload = _confirmed_json_payload(
                    registration,
                    confirmation_email_sent=getattr(registration, "_confirmation_email_sent", False),
                )
                payload["message"] = "Registration confirmed. Your seat is reserved."
                return JsonResponse(payload)
            messages.success(request, "Registration confirmed. Your seat is reserved.")
            return redirect("event_registration_confirmation", token=registration.registration_token)

    if registration.participant_type == EventRegistration.TYPE_MAKONBOOK:
        if getattr(request.user, "is_authenticated", False):
            back_url = reverse("events")
        else:
            back_url = reverse("event_registration_student", kwargs={"slug": event.slug})
    else:
        back_url = reverse("event_registration_external", kwargs={"slug": event.slug})

    context = {
        "event": event,
        "registration": registration,
        "masked_email": masked_email(registration.email),
        "expired": bool(registration.verification_expires_at and timezone.now() >= registration.verification_expires_at),
        "registration_back_url": back_url,
    }
    return render(request, "sat/events/register_verify.html", context)


@require_POST
def event_registration_resend(request, token):
    registration = get_object_or_404(
        EventRegistration.objects.select_related("event"),
        registration_token=token,
    )
    if registration.status == EventRegistration.STATUS_CONFIRMED:
        confirmation_url = reverse("event_registration_confirmation", kwargs={"token": registration.registration_token})
        if _wants_json(request):
            return JsonResponse(_confirmed_json_payload(registration))
        return redirect("event_registration_confirmation", token=registration.registration_token)
    try:
        send_registration_code(request, registration)
    except EventRegistrationError as exc:
        if _wants_json(request):
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        messages.error(request, str(exc))
    else:
        if _wants_json(request):
            registration.refresh_from_db(fields=["verification_expires_at", "verification_attempts"])
            return JsonResponse({
                "ok": True,
                "message": "A new verification code has been sent.",
                "masked_email": masked_email(registration.email),
            })
        messages.success(request, "A new verification code has been sent.")
    return redirect("event_registration_verify", token=registration.registration_token)


def event_registration_confirmation(request, token):
    registration = get_object_or_404(
        EventRegistration.objects.select_related("event", "user", "guest", "event__test"),
        registration_token=token,
        status=EventRegistration.STATUS_CONFIRMED,
    )
    # The UUID token is the recovery key for external participants. For MakonBook
    # accounts, require the signed-in owner unless this browser already owns the
    # confirmed registration session.
    if registration.user_id and getattr(request.user, "is_authenticated", False) and request.user.pk != registration.user_id:
        messages.error(request, "This registration belongs to another MakonBook account.")
        return redirect("home")

    from .event_registration import bind_registration_to_session
    bind_registration_to_session(request, registration)

    context = {
        "event": registration.event,
        "registration": registration,
        "registration_id": registration.registration_id,
        "availability": getattr(registration.event, "is_live_now", False),
    }
    return render(request, "sat/events/register_confirmation.html", context)

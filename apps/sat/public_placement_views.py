from __future__ import annotations

import hashlib
import hmac
import re
import time

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .guest_views import (
    _guest_attempt_expiry,
    _questions_for_step,
    get_client_ip,
)
from .models import (
    GlobalEvent,
    GlobalEventAttempt,
    GuestParticipant,
    PlacementTelegramNotification,
    PublicPlacementLead,
)
from .views import get_test_sequence


PHONE_RE = re.compile(r"^\+998\d{9}$")


def _public_placement_queryset():
    return (
        GlobalEvent.objects.filter(
            event_type=GlobalEvent.TYPE_PLACEMENT,
            is_public=True,
            status__in=["live", "scheduled"],
            registration_enabled=False,
            access_code="",
        )
        .select_related("test")
        .order_by("start_at", "title")
    )


def _public_placement_digest(value: str) -> str:
    secret = (settings.SECRET_KEY or "makonbook").encode("utf-8", errors="ignore")
    return hmac.new(secret, value.encode("utf-8", errors="ignore"), hashlib.sha256).hexdigest()


def _public_placement_rate_allowed(request, phone: str) -> tuple[bool, int]:
    """Small abuse guard: 12 valid starts/IP/hour and 3 starts/phone/hour."""
    raw_ip = get_client_ip(request) or "unknown"
    now = int(time.time())
    window = 3600
    retry_after = max(1, window - (now % window))
    window_id = now // window
    checks = (
        ("ip", raw_ip, 12),
        ("phone", phone, 3),
    )
    try:
        for scope, raw, limit in checks:
            key = f"placement:v5610:{scope}:{window_id}:{_public_placement_digest(raw)}"
            cache.add(key, 0, timeout=window + 5)
            if cache.incr(key) > limit:
                return False, retry_after
    except Exception:
        # Placement must not go down because Redis/cache is temporarily unavailable.
        return True, 0
    return True, 0


def normalize_public_phone(value: str) -> str:
    raw = re.sub(r"[^0-9+]", "", str(value or "").strip())
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("998") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 9:
        return "+998" + digits
    return raw


def _clean_name(value: str) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:80]


def _decorate_public_placement_event(event):
    """Attach display-only metadata without adding another persisted model."""
    sequence = get_test_sequence(event.test)
    question_count = 0
    duration_minutes = 0
    sections = []
    for section, module in sequence:
        question_count += len(_questions_for_step(event.test, section, module))
        duration_minutes += int(event.get_module_duration(section) or 0)
        if section not in sections:
            sections.append(section)

    event.public_question_count = question_count
    event.public_module_count = len(sequence)
    event.public_duration_minutes = duration_minutes
    event.public_sections = sections
    return event


def public_placement_list(request):
    now = timezone.now()
    GlobalEvent.close_expired(now)
    events = [_decorate_public_placement_event(event) for event in _public_placement_queryset()]
    live_events = [event for event in events if event.is_live_now]
    upcoming_events = [
        event for event in events
        if not event.is_live_now and event.status == "scheduled" and event.start_at and event.start_at > now
    ]
    return render(
        request,
        "sat/public_placement/list.html",
        {
            "live_events": live_events,
            "upcoming_events": upcoming_events,
            "live_count": len(live_events),
        },
    )


def public_placement_start(request, slug):
    event = get_object_or_404(_public_placement_queryset(), slug=slug)
    sequence = get_test_sequence(event.test)
    total_questions = sum(
        len(_questions_for_step(event.test, section, module))
        for section, module in sequence
    )

    estimated_minutes = sum(int(event.get_module_duration(section) or 0) for section, _module in sequence)
    sections = []
    for section, _module in sequence:
        if section not in sections:
            sections.append(section)

    context = {
        "event": event,
        "total_questions": total_questions,
        "estimated_minutes": estimated_minutes,
        "module_count": len(sequence),
        "section_count": len(sections),
        "can_start": bool(event.is_live_now and sequence and total_questions),
        "form": {},
        "errors": {},
    }

    if request.method != "POST":
        return render(request, "sat/public_placement/start.html", context)

    # Honeypot: silently drop obvious form-bot submissions.
    if (request.POST.get("website") or "").strip():
        return redirect("public_placement_list")

    first_name = _clean_name(request.POST.get("first_name"))
    last_name = _clean_name(request.POST.get("last_name"))
    phone = normalize_public_phone(request.POST.get("phone_number"))
    consent = request.POST.get("consent_to_contact") == "1"
    context["form"] = {
        "first_name": first_name,
        "last_name": last_name,
        "phone_number": phone,
        "consent_to_contact": consent,
    }

    errors = {}
    if len(first_name) < 2:
        errors["first_name"] = "Enter your first name."
    if len(last_name) < 2:
        errors["last_name"] = "Enter your last name."
    if not PHONE_RE.fullmatch(phone):
        errors["phone_number"] = "Enter a valid Uzbekistan phone number, for example +998 90 123 45 67."
    if not consent:
        errors["consent_to_contact"] = "Consent is required so MakonBook can contact you about the placement result."
    if not event.is_live_now:
        errors["event"] = "This placement test is not available right now."
    if not sequence or not total_questions:
        errors["event"] = "This placement test does not contain any available questions yet."

    if not errors:
        allowed, retry_after = _public_placement_rate_allowed(request, phone)
        if not allowed:
            errors["rate"] = f"Too many placement starts. Try again in about {max(1, retry_after // 60)} minutes."

    if errors:
        context["errors"] = errors
        return render(request, "sat/public_placement/start.html", context, status=429 if "rate" in errors else 400)

    if not request.session.session_key:
        request.session.create()

    with transaction.atomic():
        full_name = f"{first_name} {last_name}".strip()
        guest = GuestParticipant.objects.create(
            full_name=full_name,
            display_name=full_name,
            session_key=request.session.session_key or "",
            first_ip=get_client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:2000],
        )
        attempt = GlobalEventAttempt.objects.create(
            event=event,
            guest=guest,
            expires_at=_guest_attempt_expiry(event, sequence),
            total_questions=total_questions,
        )
        lead = PublicPlacementLead.objects.create(
            event=event,
            guest=guest,
            attempt=attempt,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone,
            consent_to_contact=True,
        )
        PlacementTelegramNotification.objects.get_or_create(
            lead=lead,
            kind=PlacementTelegramNotification.KIND_STARTED,
        )

    request.session["guest_mode"] = True
    request.session["guest_id"] = str(guest.guest_id)
    request.session["guest_name"] = full_name
    request.session["public_placement_guest"] = True
    request.session["public_placement_lead_id"] = lead.pk
    request.session.modified = True

    return redirect("global_event_attempt_root", guest_token=attempt.guest_token)

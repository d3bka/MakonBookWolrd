from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string

from .models import EventRegistration, GlobalEvent, GuestParticipant


logger = logging.getLogger(__name__)


class EventRegistrationError(Exception):
    pass


class EmailValidationError(EventRegistrationError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_email",
        suggested_email: str = "",
        can_override: bool = False,
    ):
        super().__init__(message)
        self.code = code
        self.suggested_email = suggested_email
        self.can_override = can_override


@dataclass(frozen=True)
class EmailAssessment:
    email: str
    status: str
    suggested_email: str = ""


# Provider typos are intentionally conservative. We never auto-correct an
# address: MakonBook asks the participant to review it and explicitly choose
# whether to update the profile or send anyway.
_COMMON_EMAIL_DOMAINS = (
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "yahoo.com",
    "icloud.com",
    "mail.ru",
    "yandex.ru",
)

_EXACT_EMAIL_DOMAIN_TYPOS = {
    # Gmail
    "gml.co": "gmail.com",
    "gml.com": "gmail.com",
    "gmail.co": "gmail.com",
    "gmail.cm": "gmail.com",
    "gmail.con": "gmail.com",
    "gmail.cmo": "gmail.com",
    "gmail.comm": "gmail.com",
    "gmai.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gmaill.com": "gmail.com",
    # Outlook / Hotmail
    "outlok.com": "outlook.com",
    "outloo.com": "outlook.com",
    "outlook.co": "outlook.com",
    "outlook.con": "outlook.com",
    "hotmai.com": "hotmail.com",
    "hotmal.com": "hotmail.com",
    "hotmial.com": "hotmail.com",
    "hotmail.co": "hotmail.com",
    # Yahoo / iCloud
    "yaho.com": "yahoo.com",
    "yahoo.co": "yahoo.com",
    "yahoo.con": "yahoo.com",
    "iclod.com": "icloud.com",
    "icoud.com": "icloud.com",
    "icloud.co": "icloud.com",
}


def _email_domain_distance(left: str, right: str) -> int:
    """Small Levenshtein implementation; domains here are tiny strings."""
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, lch in enumerate(left, start=1):
        current = [i]
        for j, rch in enumerate(right, start=1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (lch != rch),
            ))
        previous = current
    return previous[-1]


def _suggest_email_domain(domain: str) -> str:
    domain = (domain or "").strip().lower().rstrip(".")
    if not domain or domain in _COMMON_EMAIL_DOMAINS:
        return ""
    exact = _EXACT_EMAIL_DOMAIN_TYPOS.get(domain)
    if exact:
        return exact

    # Only fuzzy-match well-known consumer providers. A business/school domain
    # must not be silently treated as a typo just because its name is similar.
    ranked = sorted(
        ((_email_domain_distance(domain, candidate), candidate) for candidate in _COMMON_EMAIL_DOMAINS),
        key=lambda item: item[0],
    )
    if not ranked:
        return ""
    distance, candidate = ranked[0]
    threshold = 1 if len(domain) <= 6 else 2
    return candidate if distance <= threshold else ""


def assess_registration_email(value: str) -> EmailAssessment:
    email = normalize_email(value)
    if not email:
        return EmailAssessment(email=email, status="invalid")
    try:
        validate_email(email)
    except ValidationError:
        return EmailAssessment(email=email, status="invalid")

    local, domain = email.rsplit("@", 1)
    suggested_domain = _suggest_email_domain(domain)
    if suggested_domain:
        return EmailAssessment(
            email=email,
            status="suspicious",
            suggested_email=f"{local}@{suggested_domain}",
        )
    return EmailAssessment(email=email, status="valid")


def validate_registration_email(value: str, *, allow_suspicious: bool = False) -> str:
    assessment = assess_registration_email(value)
    if assessment.status == "invalid":
        raise EmailValidationError(
            "Enter a valid email address before we send a verification code.",
            code="invalid_email",
        )
    if assessment.status == "suspicious" and not allow_suspicious:
        raise EmailValidationError(
            "Please check your email address. The domain looks unusual.",
            code="suspicious_email",
            suggested_email=assessment.suggested_email,
            can_override=True,
        )
    return assessment.email


@dataclass(frozen=True)
class RegistrationWindow:
    state: str
    label: str
    can_register: bool


def normalize_name(value: str) -> str:
    return " ".join((value or "").replace("\x00", "").split())[:255]


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()[:254]


def normalize_phone(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    digits = re.sub(r"\D+", "", raw)
    if raw.startswith("+"):
        normalized = "+" + digits
    elif digits.startswith("998"):
        normalized = "+" + digits
    else:
        normalized = "+" + digits if digits else ""
    if normalized and not re.fullmatch(r"\+\d{10,15}", normalized):
        raise EventRegistrationError("Enter a valid phone number including country code.")
    return normalized


def normalize_telegram(value: str) -> str:
    value = (value or "").strip().lstrip("@")
    if not value:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", value):
        raise EventRegistrationError("Enter a valid Telegram username or leave it blank.")
    return "@" + value


def client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def registration_window(event: GlobalEvent, now=None) -> RegistrationWindow:
    now = now or timezone.now()
    if not event.registration_enabled:
        return RegistrationWindow("disabled", "Registration unavailable", False)
    if event.status == "closed":
        return RegistrationWindow("closed", "Registration closed", False)
    if event.registration_opens_at and now < event.registration_opens_at:
        return RegistrationWindow("upcoming", "Registration opens soon", False)
    if event.registration_closes_at and now > event.registration_closes_at:
        return RegistrationWindow("closed", "Registration closed", False)
    if event.capacity and event_reserved_count(event, now=now) >= event.capacity:
        return RegistrationWindow("full", "Registration is full", False)
    return RegistrationWindow("open", "Registration open", True)


def _active_seat_filter(now):
    return Q(status__in=[EventRegistration.STATUS_CONFIRMED, EventRegistration.STATUS_ATTENDED, EventRegistration.STATUS_NO_SHOW]) | Q(
        status=EventRegistration.STATUS_PENDING,
        verification_expires_at__gt=now,
    )


def expire_stale_pending(event: GlobalEvent | None = None, now=None) -> int:
    now = now or timezone.now()
    qs = EventRegistration.objects.filter(
        status=EventRegistration.STATUS_PENDING,
        verification_expires_at__isnull=False,
        verification_expires_at__lte=now,
    )
    if event is not None:
        qs = qs.filter(event=event)
    return qs.update(status=EventRegistration.STATUS_EXPIRED, verification_code_hash="")


def event_reserved_count(event: GlobalEvent, now=None) -> int:
    now = now or timezone.now()
    return event.registrations.filter(_active_seat_filter(now)).count()


def event_confirmed_count(event: GlobalEvent) -> int:
    return event.registrations.filter(
        status__in=[EventRegistration.STATUS_CONFIRMED, EventRegistration.STATUS_ATTENDED, EventRegistration.STATUS_NO_SHOW]
    ).count()


def event_pending_hold_count(event: GlobalEvent, now=None) -> int:
    """Count unexpired OTP registrations that are temporarily holding a seat."""
    now = now or timezone.now()
    return event.registrations.filter(
        status=EventRegistration.STATUS_PENDING,
        verification_expires_at__gt=now,
    ).count()


def seats_left(event: GlobalEvent, now=None):
    if not event.capacity:
        return None
    return max(0, event.capacity - event_reserved_count(event, now=now))


def _lock_capacity(event_id: int) -> GlobalEvent:
    event = GlobalEvent.objects.select_for_update().get(pk=event_id)
    expire_stale_pending(event)
    if event.capacity and event_reserved_count(event) >= event.capacity:
        raise EventRegistrationError("Registration is full for this event.")
    return event


def _verification_expiry(event: GlobalEvent):
    minutes = max(3, min(int(event.verification_minutes or 10), 30))
    return timezone.now() + timedelta(minutes=minutes)


def _prepare_pending(registration: EventRegistration) -> str:
    code = get_random_string(6, allowed_chars="0123456789")
    registration.status = EventRegistration.STATUS_PENDING
    registration.verification_code_hash = make_password(code)
    registration.verification_expires_at = _verification_expiry(registration.event)
    registration.verification_sent_at = timezone.now()
    registration.verification_attempts = 0
    registration.save(update_fields=[
        "status",
        "verification_code_hash",
        "verification_expires_at",
        "verification_sent_at",
        "verification_attempts",
        "updated_at",
    ])
    return code


def _send_verification_email(request, registration: EventRegistration, code: str) -> None:
    event = registration.event
    login_url = request.build_absolute_uri(reverse("event_registration_verify", kwargs={"token": registration.registration_token}))
    context = {
        "registration": registration,
        "event": event,
        "code": code,
        "expires_minutes": max(3, min(int(event.verification_minutes or 10), 30)),
        "verify_url": login_url,
        "current_year": timezone.localdate().year,
    }
    text_body = render_to_string("emails/mock_event_verification.txt", context)
    html_body = render_to_string("emails/mock_event_verification.html", context)
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", "")
    support_email = getattr(settings, "EMAIL_HOST_USER", "") or None
    message = EmailMultiAlternatives(
        subject=f"{event.title} — verification code",
        body=text_body,
        from_email=from_email,
        to=[registration.email],
        reply_to=[support_email] if support_email else None,
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def _send_confirmation_email(request, registration: EventRegistration) -> None:
    """Send the post-verification event checklist and registration ID.

    The OTP email proves ownership of the address. This second email is the
    participant's durable confirmation/checklist and is intentionally sent only
    after the registration changes to CONFIRMED.
    """
    event = registration.event
    confirmation_url = request.build_absolute_uri(
        reverse("event_registration_confirmation", kwargs={"token": registration.registration_token})
    )
    context = {
        "registration": registration,
        "event": event,
        "registration_id": registration.registration_id,
        "confirmation_url": confirmation_url,
        "current_year": timezone.localdate().year,
    }
    text_body = render_to_string("emails/mock_event_confirmation.txt", context)
    html_body = render_to_string("emails/mock_event_confirmation.html", context)
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", "")
    support_email = getattr(settings, "EMAIL_HOST_USER", "") or None
    message = EmailMultiAlternatives(
        subject=f"{event.title} — registration confirmed",
        body=text_body,
        from_email=from_email,
        to=[registration.email],
        reply_to=[support_email] if support_email else None,
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def send_registration_code(request, registration: EventRegistration, *, force=False) -> None:
    now = timezone.now()
    if not force and registration.verification_sent_at and registration.verification_sent_at > now - timedelta(seconds=60):
        raise EventRegistrationError("A code was sent recently. Wait a minute before requesting another one.")
    code = _prepare_pending(registration)
    try:
        _send_verification_email(request, registration, code)
    except Exception as exc:
        registration.verification_code_hash = ""
        registration.verification_expires_at = None
        registration.save(update_fields=["verification_code_hash", "verification_expires_at", "updated_at"])
        if settings.DEBUG:
            raise EventRegistrationError(f"Verification email could not be sent: {exc}") from exc
        raise EventRegistrationError("Verification email could not be sent. Contact SATMakon staff.") from exc


def reserve_external(
    request,
    event: GlobalEvent,
    *,
    full_name: str,
    phone: str,
    email: str,
    telegram: str = "",
    allow_suspicious_email: bool = False,
) -> EventRegistration:
    full_name = normalize_name(full_name)
    email = normalize_email(email)
    phone = normalize_phone(phone)
    telegram = normalize_telegram(telegram)
    if not full_name:
        raise EventRegistrationError("Full name is required.")
    email = validate_registration_email(email, allow_suspicious=allow_suspicious_email)
    if not phone:
        raise EventRegistrationError("Phone number is required.")

    window = registration_window(event)
    if not window.can_register:
        raise EventRegistrationError(window.label + ".")

    with transaction.atomic():
        locked = _lock_capacity(event.pk)
        duplicate = EventRegistration.objects.select_for_update().filter(event=locked).filter(
            Q(email__iexact=email) | Q(phone=phone)
        ).exclude(status__in=[EventRegistration.STATUS_CANCELLED, EventRegistration.STATUS_EXPIRED]).order_by("-created_at").first()
        if duplicate:
            if duplicate.status == EventRegistration.STATUS_CONFIRMED:
                raise EventRegistrationError("This email or phone number is already registered for the event.")
            registration = duplicate
            registration.full_name = full_name
            registration.phone = phone
            registration.email = email
            registration.telegram_username = telegram
            registration.source_ip = client_ip(request)
            registration.user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:2000]
            registration.save(update_fields=["full_name", "phone", "email", "telegram_username", "source_ip", "user_agent", "updated_at"])
        else:
            registration = EventRegistration.objects.create(
                event=locked,
                participant_type=EventRegistration.TYPE_EXTERNAL,
                full_name=full_name,
                phone=phone,
                email=email,
                telegram_username=telegram,
                source_ip=client_ip(request),
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:2000],
                verification_expires_at=_verification_expiry(locked),
            )

    send_registration_code(request, registration, force=True)
    return registration


def _phone_variants(identifier: str) -> list[str]:
    try:
        normalized = normalize_phone(identifier)
    except EventRegistrationError:
        return []
    if not normalized:
        return []
    digits = normalized.lstrip("+")
    return list(dict.fromkeys([normalized, digits]))


def is_makonbook_student_account(user) -> bool:
    """Return True for an active MakonBook student-facing account.

    Event registration verifies a MakonBook account, not the provenance of the
    account record. New public student sign-up is already disabled, so requiring
    ``hollihop_client_id`` here only breaks legitimate legacy/student accounts
    that already use the MakonBook student workspace. Staff accounts remain
    excluded.
    """
    if not user or not getattr(user, "is_active", False):
        return False
    try:
        from .student_workspace import should_use_student_workspace
        return bool(should_use_student_workspace(user))
    except Exception:
        return False


def verification_email_for_user(user) -> str:
    """Return the email MakonBook should use for event OTP verification."""
    email = normalize_email(getattr(user, "email", "") or "")
    if email:
        return email
    # allauth can hold a primary/verified address even when legacy auth_user.email
    # is blank. Use it as a safe fallback so Profile/account migrations do not
    # strand an otherwise valid student.
    try:
        from allauth.account.models import EmailAddress
        row = (
            EmailAddress.objects.filter(user=user)
            .order_by("-primary", "-verified", "id")
            .first()
        )
        if row:
            return normalize_email(row.email)
    except Exception:
        pass
    return ""


def find_makonbook_student_candidates(identifier: str) -> list:
    """Return exact active MakonBook student-account matches.

    Names are never identity keys. This compatibility helper may still accept
    email/phone for internal tooling, while the public mock flow itself uses an
    exact username before asking for the password.
    """
    identifier = (identifier or "").strip()
    if not identifier:
        return []
    User = get_user_model()
    query = Q(username__iexact=identifier) | Q(email__iexact=identifier)
    variants = _phone_variants(identifier)
    if variants:
        query |= Q(profile__phone_number__in=variants)
    rows = list(
        User.objects.filter(query, is_active=True)
        .select_related("profile")
        .prefetch_related("groups")
        .order_by("id")[:20]
    )
    return [user for user in rows if is_makonbook_student_account(user)][:10]


def find_makonbook_student(identifier: str):
    matches = find_makonbook_student_candidates(identifier)
    return matches[0] if len(matches) == 1 else None


def find_makonbook_student_by_username(username: str):
    """Return one active student-facing MakonBook account by exact username."""
    username = (username or "").strip()
    if not username:
        return None
    User = get_user_model()
    user = (
        User.objects.filter(username__iexact=username, is_active=True)
        .select_related("profile")
        .prefetch_related("groups")
        .order_by("id")
        .first()
    )
    return user if is_makonbook_student_account(user) else None


# Backward-compatible names for old imports/tests. Their semantics are now
# MakonBook-student based rather than requiring a Hollihop foreign key.
find_hollihop_student_candidates = find_makonbook_student_candidates
find_hollihop_student = find_makonbook_student
find_hollihop_student_by_username = find_makonbook_student_by_username


def reserve_makonbook_student(
    request,
    event: GlobalEvent,
    user,
    *,
    allow_suspicious_email: bool = False,
) -> EventRegistration:
    if not is_makonbook_student_account(user):
        raise EventRegistrationError("This MakonBook account is not available for student event registration.")
    profile = getattr(user, "profile", None)
    email = verification_email_for_user(user)
    if not email:
        raise EmailValidationError(
            "Add an email address in your MakonBook Profile before registering for this event.",
            code="missing_email",
        )
    email = validate_registration_email(email, allow_suspicious=allow_suspicious_email)
    full_name = normalize_name(user.get_full_name() or user.get_username())
    phone = ""
    try:
        phone = normalize_phone(profile.phone_number or "")
    except EventRegistrationError:
        phone = ""

    window = registration_window(event)
    if not window.can_register:
        existing = EventRegistration.objects.filter(event=event, user=user).first()
        if existing and existing.status == EventRegistration.STATUS_CONFIRMED:
            return existing
        raise EventRegistrationError(window.label + ".")

    with transaction.atomic():
        locked = _lock_capacity(event.pk)
        registration, created = EventRegistration.objects.select_for_update().get_or_create(
            event=locked,
            user=user,
            defaults={
                "participant_type": EventRegistration.TYPE_MAKONBOOK,
                "full_name": full_name,
                "phone": phone,
                "email": email,
                "source_ip": client_ip(request),
                "user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:2000],
                "verification_expires_at": _verification_expiry(locked),
            },
        )
        if not created:
            if registration.status == EventRegistration.STATUS_CONFIRMED:
                return registration
            registration.participant_type = EventRegistration.TYPE_MAKONBOOK
            registration.full_name = full_name
            registration.phone = phone
            registration.email = email
            registration.source_ip = client_ip(request)
            registration.user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:2000]
            registration.save(update_fields=["participant_type", "full_name", "phone", "email", "source_ip", "user_agent", "updated_at"])

    send_registration_code(request, registration, force=True)
    return registration


def verify_registration(request, registration: EventRegistration, code: str) -> EventRegistration:
    code = (code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        raise EventRegistrationError("Enter the 6-digit verification code.")

    newly_confirmed = False
    with transaction.atomic():
        # PostgreSQL refuses FOR UPDATE when the query also locks nullable
        # OUTER JOIN targets (user/guest). Lock only the registration row;
        # related objects are loaded lazily after the row lock is acquired.
        registration = EventRegistration.objects.select_for_update().get(pk=registration.pk)
        if registration.status == EventRegistration.STATUS_CONFIRMED:
            bind_registration_to_session(request, registration)
            return registration
        if (
            registration.participant_type == EventRegistration.TYPE_MAKONBOOK
            and registration.user_id
            and getattr(request.user, "is_authenticated", False)
            and request.user.pk != registration.user_id
        ):
            raise EventRegistrationError("This registration belongs to another MakonBook account.")
        if registration.status not in {EventRegistration.STATUS_PENDING, EventRegistration.STATUS_EXPIRED}:
            raise EventRegistrationError("This registration can no longer be verified.")
        if not registration.verification_expires_at or timezone.now() >= registration.verification_expires_at:
            registration.status = EventRegistration.STATUS_EXPIRED
            registration.verification_code_hash = ""
            registration.save(update_fields=["status", "verification_code_hash", "updated_at"])
            raise EventRegistrationError("The verification code expired. Request a new code.")
        if registration.verification_attempts >= 5:
            raise EventRegistrationError("Too many incorrect attempts. Request a new verification code.")
        if not registration.verification_code_hash or not check_password(code, registration.verification_code_hash):
            registration.verification_attempts += 1
            registration.save(update_fields=["verification_attempts", "updated_at"])
            raise EventRegistrationError("Invalid verification code.")

        if registration.guest_id is None:
            if not request.session.session_key:
                request.session.create()
            guest = GuestParticipant.objects.create(
                full_name=registration.full_name,
                display_name=registration.full_name,
                session_key=request.session.session_key or "",
                first_ip=client_ip(request),
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:2000],
            )
            registration.guest = guest

        registration.status = EventRegistration.STATUS_CONFIRMED
        registration.verified_at = timezone.now()
        registration.verification_code_hash = ""
        registration.verification_attempts = 0
        registration.save(update_fields=[
            "guest",
            "status",
            "verified_at",
            "verification_code_hash",
            "verification_attempts",
            "updated_at",
        ])
        newly_confirmed = True

    # Confirmation/checklist email is best-effort: a temporary SMTP problem must
    # never roll back a valid seat reservation. The result is exposed to the
    # inline UI so staff/student can see if delivery failed.
    confirmation_email_sent = False
    if newly_confirmed:
        try:
            _send_confirmation_email(request, registration)
            confirmation_email_sent = True
        except Exception:
            logger.exception(
                "Mock registration confirmation email failed registration_id=%s event_id=%s",
                registration.registration_id,
                registration.event_id,
            )
    registration._confirmation_email_sent = confirmation_email_sent

    # Email OTP is the identity proof for SATMakon students. After a successful
    # verification, sign the owner into the real MakonBook account instead of
    # leaving the browser as an anonymous guest-only session. The hidden
    # GuestParticipant remains only as a compatibility owner for the legacy
    # GlobalEventAttempt engine.
    if registration.participant_type == EventRegistration.TYPE_MAKONBOOK and registration.user_id:
        if getattr(request.user, "is_authenticated", False) and request.user.pk != registration.user_id:
            raise EventRegistrationError("This registration belongs to another MakonBook account.")
        if not getattr(request.user, "is_authenticated", False):
            auth_login(request, registration.user, backend="apps.base.auth_backends.EmailOrPhoneModelBackend")

    bind_registration_to_session(request, registration)
    return registration


def bind_registration_to_session(request, registration: EventRegistration) -> None:
    if registration.status != EventRegistration.STATUS_CONFIRMED or registration.guest_id is None:
        return
    request.session["guest_mode"] = registration.participant_type == EventRegistration.TYPE_EXTERNAL
    request.session["guest_id"] = str(registration.guest.guest_id)
    request.session["guest_name"] = registration.full_name
    request.session["verified_event_registration"] = True
    request.session[f"event_registration_token_{registration.event_id}"] = str(registration.registration_token)
    request.session.modified = True


def registration_for_request(request, event: GlobalEvent):
    qs = EventRegistration.objects.filter(event=event, status=EventRegistration.STATUS_CONFIRMED).select_related("guest", "user", "event")
    if getattr(request.user, "is_authenticated", False):
        registration = qs.filter(user=request.user).first()
        if registration:
            bind_registration_to_session(request, registration)
        return registration
    token = request.session.get(f"event_registration_token_{event.pk}")
    if not token:
        return None
    registration = qs.filter(registration_token=token).first()
    if registration:
        bind_registration_to_session(request, registration)
    return registration


def masked_email(email: str) -> str:
    email = normalize_email(email)
    if "@" not in email:
        return "your email"
    local, domain = email.split("@", 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}{'*' * max(2, len(local) - len(visible))}@{domain}"

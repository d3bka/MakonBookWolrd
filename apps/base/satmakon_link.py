"""V84: a self-registered student proves they are a current SATMakon student.

Hollihop keeps only the student's phone. Every active SATMakon student already has a
MakonBook account made by the Hollihop sync (with that phone and their classrooms).
To join that account, the student types the phone, receives an SMS code on it, and
after the code is confirmed:

* the email and password of the new self-registered account move to the SATMakon
  account (all tests, classrooms and history live there);
* the new, empty account is closed;
* the student is signed in to the SATMakon account and has full access.

An SATMakon account that already has its own confirmed email is never taken over.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.integrations.hollihop.normalization import normalize_phone

from .models import SatmakonLinkCode, UserProfile

log = logging.getLogger("makonbook.satmakon_link")

MAX_CODE_ATTEMPTS = 5
# Must match the text approved at the SMS provider (PlayMobile) exactly.
DEFAULT_SMS_TEXT = "MakonBook: Your verification code for MakonBook is {code}"


class LinkError(Exception):
    pass


def sms_text(code):
    template = getattr(settings, "MAKONBOOK_SATMAKON_LINK_SMS_TEXT", "") or DEFAULT_SMS_TEXT
    return template.replace("{code}", code)


def candidates_for_phone(phone):
    """Active SATMakon student accounts (made by the Hollihop sync) that use this phone."""
    phone = normalize_phone(phone)
    if not phone:
        return []
    return list(
        UserProfile.objects.select_related("user")
        .filter(phone_number=phone, hollihop_client_id__isnull=False, user__is_active=True,
                hollihop_teacher_id__isnull=True, hollihop_employee_id__isnull=True)
        .order_by("user__last_name", "user__first_name", "user_id")
    )


def can_link(user):
    profile = getattr(user, "profile", None)
    return bool(profile and profile.self_registered and not profile.hollihop_client_id and user.is_active)


def send_link_code(user, phone):
    """Send an SMS code to the phone if it belongs to an active SATMakon student."""
    from apps.integrations.hollihop.sms import SmsDeliveryError, send_sms

    phone = normalize_phone(phone)
    if not phone:
        raise LinkError("Enter the phone number you gave SATMakon, for example +998 90 123 45 67.")
    if not candidates_for_phone(phone):
        raise LinkError(
            "We could not find a current SATMakon student with this number. Use the number written in "
            "your SATMakon contract, or ask your SATMakon manager to check it."
        )
    code = get_random_string(6, allowed_chars="0123456789")
    SatmakonLinkCode.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
    row = SatmakonLinkCode.objects.create(user=user, phone=phone, code_hash=make_password(code))
    provider = str(getattr(settings, "MAKONBOOK_SMS_PROVIDER", "") or "").lower()
    if provider in {"", "disabled", "none"}:
        if settings.DEBUG or getattr(settings, "MAKONBOOK_SATMAKON_LINK_TEST_CODES", False):
            log.warning("SMS is disabled; SATMakon link test code for user %s issued.", user.pk)
            return row, code  # shown on screen only in test mode
        row.delete()
        raise LinkError("SMS sending is not available right now. Please try again later.")
    template_id = str(getattr(settings, "PLAYMOBILE_VERIFICATION_TEMPLATE_ID", "") or "").strip()
    variable = str(getattr(settings, "PLAYMOBILE_VERIFICATION_TEMPLATE_VARIABLE", "") or "code").strip()
    try:
        # PlayMobile: its own approved template (id + {code} variable) when configured,
        # otherwise the approved literal text. Never the credentials template.
        send_sms(phone, sms_text(code), template_id=template_id,
                 template_variables={variable: code} if template_id else None)
    except SmsDeliveryError as exc:
        row.delete()
        log.warning("SATMakon link SMS failed for user %s: %s", user.pk, exc)
        raise LinkError("We could not send the SMS. Please try again in a few minutes.") from exc
    return row, None


def verify_link_code(user, code):
    """Check the newest code. Returns the confirmed SatmakonLinkCode row."""
    row = SatmakonLinkCode.objects.filter(user=user, used_at__isnull=True).order_by("-created_at").first()
    if row is None or row.is_expired:
        raise LinkError("The code has expired. Send a new one.")
    if row.attempts >= MAX_CODE_ATTEMPTS:
        raise LinkError("Too many wrong codes. Send a new one.")
    if not check_password(str(code or "").strip(), row.code_hash):
        row.attempts += 1
        row.save(update_fields=["attempts"])
        raise LinkError("The code is not correct.")
    row.verified_at = timezone.now()
    row.save(update_fields=["verified_at"])
    return row


def confirmed_row(user):
    """The confirmed, unused, still-fresh code row of this user, or None."""
    row = (SatmakonLinkCode.objects.filter(user=user, used_at__isnull=True, verified_at__isnull=False)
           .order_by("-verified_at").first())
    if row is None or row.is_expired:
        return None
    return row


def join_accounts(source, target_user_id, row):
    """Move the email and password of `source` (new self-registered account) to the
    SATMakon account `target_user_id`, close `source`. Returns the SATMakon user."""
    User = get_user_model()
    allowed = {profile.user_id for profile in candidates_for_phone(row.phone)}
    if int(target_user_id) not in allowed:
        raise LinkError("Choose one of the students shown for this number.")
    with transaction.atomic():
        source = User.objects.select_for_update().get(pk=source.pk)
        target = User.objects.select_for_update().get(pk=target_user_id)
        target_profile = UserProfile.objects.select_for_update().get(user=target)
        if not can_link(source):
            raise LinkError("This account is already linked.")
        if target_profile.email_verified_at:
            raise LinkError(
                "This SATMakon account is already connected to another email. Log in with it, or ask your "
                "SATMakon manager for help."
            )
        email, password_hash = source.email, source.password
        source.email = ""
        source.is_active = False
        source.save(update_fields=["email", "is_active"])
        target.email = email
        target.password = password_hash
        target.save(update_fields=["email", "password"])
        target_profile.email_verified_at = timezone.now()
        target_profile.must_change_password = False
        target_profile.save(update_fields=["email_verified_at", "must_change_password"])
        row.used_at = timezone.now()
        row.save(update_fields=["used_at"])
    log.info("SATMakon link: self-registered user %s joined SATMakon account %s", source.pk, target.pk)
    _refresh_from_hollihop(target_profile.hollihop_client_id)
    # A fresh instance: the one above caches a stale profile, and the post_save signal
    # (e.g. last_login on sign-in) would write that stale profile back.
    return User.objects.select_related("profile").get(pk=target.pk)


def _refresh_from_hollihop(client_id):
    """Best effort: ask the Hollihop worker to refresh this student's classrooms now."""
    if not client_id:
        return
    try:
        from apps.integrations.hollihop.tasks import _integration_enabled, process_student_webhook

        if not _integration_enabled():
            return
        # Fire and forget: never wait for the result store (or a missing broker) here.
        process_student_webhook.apply_async(args=["StudentUpdated", int(client_id)], ignore_result=True, retry=False)
    except Exception:  # noqa: BLE001 - linking must not fail because the queue is busy
        log.warning("Could not queue a Hollihop refresh for client %s", client_id, exc_info=True)

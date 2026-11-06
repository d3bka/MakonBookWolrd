from __future__ import annotations

import secrets

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.integrations.models import HollihopCredentialDelivery, HollihopSyncLog

from .normalization import email_is_valid, normalize_email, normalize_phone
from .sms import SmsDeliveryError, send_sms


# Temporary credentials should be easy to read from an SMS and type on a phone.
# Ambiguous characters (I/L/O/0/1) are intentionally excluded.
_PASSWORD_LETTERS = "ABCDEFGHJKMNPQRSTUVWXYZ"
_PASSWORD_DIGITS = "23456789"


def generate_temporary_password(length: int = 8) -> str:
    """Return a readable one-time password such as ``KRMH-5837``.

    The temporary password is forced to change on first login, is never stored
    in plaintext, and uses about 30 bits of randomness while remaining much
    easier to read and type than the former 14-character mixed-symbol secret.
    ``length`` is retained for API compatibility but values below/above 8 do
    not change the human-friendly 4+4 format.
    """
    letters = "".join(secrets.choice(_PASSWORD_LETTERS) for _ in range(4))
    digits = "".join(secrets.choice(_PASSWORD_DIGITS) for _ in range(4))
    return f"{letters}-{digits}"


def _login_identifier(user) -> str:
    email = normalize_email(user.email)
    if email:
        return email
    phone = normalize_phone(getattr(user.profile, "phone_number", ""))
    if phone:
        return phone
    return user.get_username()


def _sms_channel_enabled() -> bool:
    provider = str(getattr(settings, "MAKONBOOK_SMS_PROVIDER", "") or "").strip().lower()
    return provider not in {"", "disabled", "none"}


def _sms_role(profile, explicit_label: str = "") -> tuple[str, str]:
    """Return (role_key, English role label) for credential SMS."""
    explicit = str(explicit_label or "").strip().lower()
    if explicit in {"student", "teacher", "manager"}:
        role_key = explicit
    elif getattr(profile, "hollihop_client_id", None):
        role_key = "student"
    elif getattr(profile, "hollihop_teacher_id", None):
        role_key = "teacher"
    elif getattr(profile, "hollihop_employee_id", None):
        role_key = "manager"
    else:
        role_key = ""

    friendly = {
        "student": "Student",
        "teacher": "Teacher",
        "manager": "Manager",
    }.get(role_key, "")
    return role_key, friendly


def _sms_template_values(user, *, login_value: str, temporary_password: str, sms_role_label: str = "") -> dict[str, str]:
    profile = user.profile
    role_key, _ = _sms_role(profile, sms_role_label)
    # These keys match the placeholders submitted for approval to PlayMobile.
    return {
        "name": str(getattr(user, "first_name", "") or "").strip() or user.get_username(),
        "staff_type": role_key or "user",
        "Login": login_value,
        "password": temporary_password,
        "website": f"{settings.SITE_URL.rstrip('/')}/login/",
    }


def _build_sms_text(user, *, login_value: str, temporary_password: str, sms_role_label: str = "") -> str:
    values = _sms_template_values(
        user,
        login_value=login_value,
        temporary_password=temporary_password,
        sms_role_label=sms_role_label,
    )
    # Keep line-breaks and fixed text identical to the approved-template request.
    return (
        f"Salom, {values['name']}! MakonBook {values['staff_type']} akkauntingiz tayyor.\n"
        f"Login: {values['Login']}\n"
        f"Vaqtinchalik parol: {values['password']}\n"
        f"Kirish: {values['website']}\n"
        "Birinchi kirishda parolni yangilang."
    )


def can_deliver_temporary_access(user) -> bool:
    """Return True only when at least one delivery channel is currently usable.

    A phone number by itself is not enough while the SMS provider is disabled.
    This lets the profile remain ``pending`` so credentials can be delivered
    later when SMS is enabled, instead of silently rotating to an unreachable
    temporary password.
    """
    email = normalize_email(user.email)
    phone = normalize_phone(getattr(user.profile, "phone_number", ""))
    return email_is_valid(email) or (bool(phone) and _sms_channel_enabled())


def deliver_new_temporary_access(
    user,
    *,
    channels: set[str] | frozenset[str] | None = None,
    sms_role_label: str = "",
) -> HollihopCredentialDelivery:
    """Reset to a fresh temporary password and deliver it once.

    The plaintext password exists only in local variables during this function.
    It is never persisted to models or logs.
    """
    profile = user.profile
    email = normalize_email(user.email)
    phone = normalize_phone(profile.phone_number)
    allowed_channels = {"email", "sms"} if channels is None else {str(value).strip().lower() for value in channels}
    invalid_channels = allowed_channels - {"email", "sms"}
    if invalid_channels:
        raise ValueError(f"Unsupported credential delivery channel(s): {', '.join(sorted(invalid_channels))}")
    has_email = email_is_valid(email) and "email" in allowed_channels
    has_phone = bool(phone)
    has_sms = has_phone and _sms_channel_enabled() and "sms" in allowed_channels

    delivery = HollihopCredentialDelivery.objects.create(
        user=user,
        email_status="pending" if has_email else "not_available",
        sms_status="pending" if has_sms else "not_available",
        overall_status="pending" if (has_email or has_sms) else "no_contact",
    )

    if not has_email and not has_sms:
        profile.credentials_delivery_status = "no_contact"
        profile.save(update_fields=["credentials_delivery_status", "updated_at"])
        return delivery

    temporary_password = generate_temporary_password()
    previous_password_hash = user.password
    previous_must_change_password = bool(profile.must_change_password)
    user.set_password(temporary_password)
    user.save(update_fields=["password"])
    profile.must_change_password = True

    login_value = _login_identifier(user)
    sent_count = 0
    failure_count = 0

    if has_email:
        context = {
            "display_name": (user.get_full_name() or user.get_username()).strip(),
            "login": login_value,
            "temporary_password": temporary_password,
            "login_url": f"{settings.SITE_URL.rstrip('/')}/login/",
            "support_email": getattr(settings, "EMAIL_HOST_USER", "") or "support@makonbook.uz",
            "current_year": timezone.localdate().year,
        }
        try:
            text_body = render_to_string("emails/hollihop_credentials.txt", context)
            html_body = render_to_string("emails/hollihop_credentials.html", context)
            message = EmailMultiAlternatives(
                subject="Your MakonBook account is ready",
                body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email],
            )
            message.attach_alternative(html_body, "text/html")
            message.send(fail_silently=False)
            delivery.email_status = "sent"
            sent_count += 1
            HollihopSyncLog.objects.create(
                event_type="credentials_email_sent",
                entity_type="user",
                external_id=str(profile.hollihop_client_id or profile.hollihop_teacher_id or profile.hollihop_employee_id or ""),
                user=user,
                details={"channel": "email"},
            )
        except Exception as exc:  # provider failures must not roll back account creation
            delivery.email_status = "failed"
            delivery.email_error_safe = f"Email provider error ({type(exc).__name__})"[:300]
            failure_count += 1

    if has_sms:
        sms_text = _build_sms_text(
            user,
            login_value=login_value,
            temporary_password=temporary_password,
            sms_role_label=sms_role_label,
        )
        try:
            sms_result = send_sms(
                phone, sms_text,
                template_variables=_sms_template_values(
                    user,
                    login_value=login_value,
                    temporary_password=temporary_password,
                    sms_role_label=sms_role_label,
                ),
            )
            delivery.sms_status = "sent"
            sent_count += 1
            HollihopSyncLog.objects.create(
                event_type="credentials_sms_sent",
                entity_type="user",
                external_id=str(profile.hollihop_client_id or profile.hollihop_teacher_id or profile.hollihop_employee_id or ""),
                user=user,
                details={
                    "channel": "sms",
                    "provider": sms_result.provider,
                    "provider_message_id": sms_result.message_id,
                    "provider_status": sms_result.status,
                },
            )
        except SmsDeliveryError as exc:
            delivery.sms_status = "failed"
            delivery.sms_error_safe = str(exc)[:300]
            failure_count += 1
        except Exception as exc:
            delivery.sms_status = "failed"
            delivery.sms_error_safe = f"SMS provider error ({type(exc).__name__})"[:300]
            failure_count += 1

    if sent_count and failure_count:
        delivery.overall_status = "partial"
        profile.credentials_delivery_status = "partial"
    elif sent_count:
        delivery.overall_status = "sent"
        profile.credentials_delivery_status = "sent"
    else:
        delivery.overall_status = "failed"
        profile.credentials_delivery_status = "failed"
        # No channel received the newly generated password. Leaving that hash in
        # place would lock an existing user out (or make a new user's password
        # unknowable). Restore the previous authentication state atomically at
        # the model level; a later retry can generate a fresh temporary password.
        user.password = previous_password_hash
        user.save(update_fields=["password"])
        profile.must_change_password = previous_must_change_password

    delivery.completed_at = timezone.now()
    delivery.save(update_fields=[
        "email_status", "sms_status", "email_error_safe", "sms_error_safe", "overall_status", "completed_at"
    ])
    update_fields = ["must_change_password", "credentials_delivery_status", "updated_at"]
    if sent_count:
        profile.credentials_last_sent_at = timezone.now()
        update_fields.append("credentials_last_sent_at")
    profile.save(update_fields=update_fields)
    return delivery

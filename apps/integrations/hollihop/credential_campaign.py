"""V105: send logins to the people the Hollihop import created, under control.

Who: active accounts created by Hollihop (``hollihop_created``) whose credentials were
never sent (``credentials_delivery_status == "pending"``) and who never logged in. An
account somebody already uses never gets its password reset here.

How: the manager tests on 1–3 people first, then starts. Celery sends ``BATCH_SIZE``
people per task and re-queues itself after ``BATCH_PAUSE_SECONDS``; pause and stop are
checked before every batch. Each person is claimed with an atomic
``pending → sending`` update, so a duplicated task can never send twice.
"""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.base.models import UserProfile
from apps.integrations.models import CredentialCampaign

from .credentials import can_deliver_temporary_access, deliver_new_temporary_access

logger = logging.getLogger(__name__)
User = get_user_model()

BATCH_SIZE = 20
BATCH_PAUSE_SECONDS = 10
ROLES = {
    "students": ("hollihop_client_id", "Students"),
    "teachers": ("hollihop_teacher_id", "Teachers"),
    "managers": ("hollihop_employee_id", "Managers"),
}
CLAIMED = "sending"


def eligible_users(roles=None):
    roles = [r for r in (roles or ROLES) if r in ROLES]
    role_q = Q()
    for role in roles:
        role_q |= Q(**{f"profile__{ROLES[role][0]}__isnull": False})
    if not roles:
        return User.objects.none()
    return (
        User.objects.filter(role_q, is_active=True, last_login__isnull=True,
                            profile__hollihop_created=True, profile__credentials_delivery_status="pending")
        .select_related("profile")
        .order_by("id")
    )


def overview() -> list[dict]:
    rows = []
    for key, (field, label) in ROLES.items():
        qs = eligible_users([key])
        with_phone = qs.exclude(profile__phone_number__isnull=True).exclude(profile__phone_number="").count()
        with_email_only = qs.filter(Q(profile__phone_number__isnull=True) | Q(profile__phone_number="")).exclude(email="").count()
        total = qs.count()
        rows.append({"key": key, "label": label, "total": total, "with_phone": with_phone,
                     "email_only": with_email_only, "no_contact": max(0, total - with_phone - with_email_only)})
    return rows


def find_test_people(text: str, roles=None, limit: int = 3):
    """Look people up by username, user id or phone among those who would get logins."""
    from .normalization import normalize_phone

    found, missing = [], []
    for raw in [part.strip() for part in (text or "").replace(";", ",").split(",") if part.strip()][:limit]:
        qs = eligible_users(roles)
        phone = normalize_phone(raw)
        user = (
            qs.filter(username__iexact=raw).first()
            or (qs.filter(pk=int(raw)).first() if raw.isdecimal() and len(raw) < 9 else None)
            or (qs.filter(profile__phone_number=phone).first() if phone else None)
        )
        (found.append(user) if user else missing.append(raw))
    return found, missing


def send_one(user):
    """Deliver once. Returns the delivery, or None when somebody else already handled this person."""
    claimed = UserProfile.objects.filter(user_id=user.pk, credentials_delivery_status="pending").update(
        credentials_delivery_status=CLAIMED,
    )
    if not claimed:
        return None
    user = User.objects.select_related("profile").get(pk=user.pk)
    if not can_deliver_temporary_access(user):
        UserProfile.objects.filter(user_id=user.pk).update(credentials_delivery_status="no_contact")
        return "no_contact"
    try:
        return deliver_new_temporary_access(user)
    except Exception:  # noqa: BLE001 - one person must not stop the campaign
        logger.exception("Credential delivery crashed for user %s", user.pk)
        UserProfile.objects.filter(user_id=user.pk, credentials_delivery_status=CLAIMED).update(credentials_delivery_status="failed")
        return "failed"


def _count(campaign, result):
    status = result if isinstance(result, str) else getattr(result, "overall_status", "failed")
    if status == "sent":
        campaign.sent += 1
    elif status == "partial":
        campaign.partial += 1
    elif status == "no_contact":
        campaign.no_contact += 1
    else:
        campaign.failed += 1
        if not isinstance(result, str):
            campaign.last_error = (result.sms_error_safe or result.email_error_safe or "")[:300]


def run_batch(campaign_id: int) -> bool:
    """Send one batch. Returns True when another batch should follow."""
    with transaction.atomic():
        campaign = CredentialCampaign.objects.select_for_update().filter(pk=campaign_id).first()
        if not campaign or campaign.status != CredentialCampaign.STATUS_RUNNING:
            return False
        people = list(eligible_users(campaign.roles).filter(pk__gt=campaign.last_user_id)[:BATCH_SIZE])
        if not people:
            campaign.status = CredentialCampaign.STATUS_DONE
            campaign.finished_at = timezone.now()
            campaign.save(update_fields=["status", "finished_at", "updated_at"])
            return False
        campaign.last_user_id = people[-1].pk
        campaign.save(update_fields=["last_user_id", "updated_at"])
    for user in people:
        result = send_one(user)
        if result is None:
            continue
        with transaction.atomic():
            campaign = CredentialCampaign.objects.select_for_update().get(pk=campaign_id)
            _count(campaign, result)
            campaign.save(update_fields=["sent", "partial", "failed", "no_contact", "last_error", "updated_at"])
    return True


def active_campaign() -> CredentialCampaign:
    campaign = CredentialCampaign.objects.filter(
        status__in=[CredentialCampaign.STATUS_DRAFT, CredentialCampaign.STATUS_RUNNING, CredentialCampaign.STATUS_PAUSED]
    ).first()
    return campaign or CredentialCampaign.objects.create(roles=list(ROLES))

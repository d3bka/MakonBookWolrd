from __future__ import annotations

import asyncio
import html
import logging
import os
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import close_old_connections, transaction
from django.urls import reverse
from django.utils import timezone

from apps.sat.guest_views import calculate_attempt_breakdown
from apps.sat.models import PlacementTelegramNotification, PublicPlacementLead

from .models import TelegramAdmin

logger = logging.getLogger(__name__)


THREAD_START_KEY = "start_message_id"
THREAD_COMPLETION_KEY = "completion_message_id"


def _parse_chat_targets(raw: str) -> list[str | int]:
    values: list[str | int] = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            value: str | int = int(item)
        except ValueError:
            value = item
        if value not in values:
            values.append(value)
    return values


def _configured_group_destinations() -> list[str | int]:
    """Explicit Placement routing targets. A configured group is the primary route."""
    return _parse_chat_targets(os.getenv("TELEGRAM_PLACEMENT_CHAT_ID") or "")


def _configured_admin_destinations() -> list[int]:
    return list(
        TelegramAdmin.objects.filter(is_active=True).values_list("telegram_id", flat=True)
    )


def _chat_key(chat_id: str | int) -> str:
    return str(chat_id)


def _thread_refs(payload: dict, chat_id: str | int) -> dict:
    threads = payload.get("telegram_threads") or {}
    if not isinstance(threads, dict):
        return {}
    refs = threads.get(_chat_key(chat_id)) or {}
    return refs if isinstance(refs, dict) else {}


def _message_id_from_result(result) -> int | None:
    message_id = getattr(result, "message_id", None)
    if message_id is None and isinstance(result, dict):
        message_id = result.get("message_id")
    try:
        return int(message_id) if message_id is not None else None
    except (TypeError, ValueError):
        return None


def _store_thread_message_id(
    lead_id: int,
    chat_id: str | int,
    field: str,
    message_id: int,
):
    """Persist a Telegram message link without losing refs written by another worker."""
    if field not in {THREAD_START_KEY, THREAD_COMPLETION_KEY}:
        raise ValueError(f"Unsupported Telegram thread field: {field}")

    close_old_connections()
    with transaction.atomic():
        lead = PublicPlacementLead.objects.select_for_update().filter(pk=lead_id).first()
        if not lead:
            return
        threads = dict(lead.telegram_threads or {})
        key = _chat_key(chat_id)
        refs = dict(threads.get(key) or {})
        refs[field] = int(message_id)
        threads[key] = refs
        lead.telegram_threads = threads
        lead.save(update_fields=["telegram_threads", "updated_at"])


def _notification_snapshot(notification_id: int):
    close_old_connections()
    notice = (
        PlacementTelegramNotification.objects.select_related(
            "lead", "lead__event", "lead__attempt", "lead__attempt__event", "lead__attempt__event__test"
        )
        .filter(pk=notification_id)
        .first()
    )
    if not notice:
        return None
    lead = notice.lead
    admin_url = ""
    try:
        admin_url = f"{settings.SITE_URL.rstrip('/')}{reverse('admin:sat_publicplacementlead_change', args=[lead.pk])}"
    except Exception:
        admin_url = ""

    elapsed_minutes = None
    if lead.started_at and (lead.completed_at or (lead.attempt and lead.attempt.submitted_at)):
        completed_at = lead.completed_at or lead.attempt.submitted_at
        elapsed_minutes = max(1, int((completed_at - lead.started_at).total_seconds() // 60))

    payload = {
        "id": notice.pk,
        "lead_id": lead.pk,
        "kind": notice.kind,
        "name": lead.full_name,
        "phone": lead.phone_number,
        "event": lead.event.title,
        "started_at": lead.started_at,
        "completed_at": lead.completed_at,
        "attempt_id": lead.attempt_id,
        "attempts": notice.attempts,
        "admin_url": admin_url,
        "elapsed_minutes": elapsed_minutes,
        "telegram_threads": dict(lead.telegram_threads or {}),
    }
    if notice.kind == PlacementTelegramNotification.KIND_COMPLETED and lead.attempt_id:
        breakdown = calculate_attempt_breakdown(lead.attempt)
        total_questions = breakdown.get("placement_total_questions") or lead.attempt.total_questions or 0
        raw = breakdown.get("total_raw") or 0
        payload.update(
            {
                "total_score": breakdown.get("total_score"),
                "scoring_label": breakdown.get("scoring_label"),
                "placement": breakdown.get("placement"),
                "raw": raw,
                "total_questions": total_questions,
                "percentage": round((raw / total_questions) * 100, 1) if total_questions else 0,
            }
        )
    return payload


def _format_clock(value) -> str:
    if not value:
        return "—"
    try:
        return timezone.localtime(value).strftime("%H:%M")
    except Exception:
        return "—"


def _format_duration(minutes) -> str:
    try:
        minutes = int(minutes or 0)
    except (TypeError, ValueError):
        minutes = 0
    if minutes <= 0:
        return "<1 min"
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins} min"


def _result_lines(payload: dict) -> list[str]:
    placement = payload.get("placement") or {}
    lines: list[str] = []
    if placement:
        lines.append(f"🎯 Level: <b>{html.escape(str(placement.get('label') or '—'))}</b>")
        lines.append(f"📊 Result: <b>{payload.get('percentage', 0)}%</b>")
    elif payload.get("total_score"):
        lines.append(f"🎯 Score: <b>{payload['total_score']}</b>")
        if payload.get("scoring_label"):
            lines.append(f"📊 {html.escape(str(payload['scoring_label']))}")
    else:
        lines.append(
            f"📊 Result: <b>{payload.get('raw', 0)} / {payload.get('total_questions', 0)}"
            f" · {payload.get('percentage', 0)}%</b>"
        )
    return lines


def _result_summary(payload: dict) -> str:
    placement = payload.get("placement") or {}
    if placement:
        label = html.escape(str(placement.get("label") or "Level"))
        return f"{label} · {payload.get('percentage', 0)}%"
    if payload.get("total_score"):
        return str(payload["total_score"])
    return f"{payload.get('percentage', 0)}%"


def _format_message(payload: dict) -> str:
    name = html.escape(str(payload.get("name") or "—"))
    phone = html.escape(str(payload.get("phone") or "—"))
    event = html.escape(str(payload.get("event") or "Placement Test"))
    admin_url = html.escape(str(payload.get("admin_url") or ""), quote=True)
    attempt_id = payload.get("attempt_id")
    lead_id = payload.get("lead_id")

    if payload.get("kind") == PlacementTelegramNotification.KIND_STARTED:
        lines = [
            "🟡 <b>EXAM IN PROGRESS</b>",
            "",
            f"👤 <b>{name}</b>",
            f"📞 <code>{phone}</code>",
            f"📝 {event}",
        ]
        if attempt_id:
            lines.append(f"🆔 Attempt #{attempt_id}")
        if lead_id:
            lines.append(f"🔖 Lead #{lead_id}")
        lines.extend(
            [
                "",
                f"🕐 Started: <b>{_format_clock(payload.get('started_at'))}</b>",
                "⏳ Status: <b>In progress...</b>",
            ]
        )
        if admin_url:
            lines.extend(["", f'🔎 <a href="{admin_url}">Open lead in MakonBook</a>'])
        return "\n".join(lines)

    lines = [
        "✅ <b>EXAM COMPLETED</b>",
        "",
        f"👤 <b>{name}</b>",
        f"📞 <code>{phone}</code>",
        f"📝 {event}",
    ]
    if attempt_id:
        lines.append(f"🆔 Attempt #{attempt_id}")
    if lead_id:
        lines.append(f"🔖 Lead #{lead_id}")

    lines.extend(
        [
            "",
            f"🕐 Started: <b>{_format_clock(payload.get('started_at'))}</b>",
            f"🏁 Finished: <b>{_format_clock(payload.get('completed_at'))}</b>",
            f"⏱ Duration: <b>{_format_duration(payload.get('elapsed_minutes'))}</b>",
            "",
        ]
    )
    lines.extend(_result_lines(payload))
    lines.extend(["", "🟢 Status: <b>Completed</b>"])
    if admin_url:
        lines.extend(["", f'🔎 <a href="{admin_url}">Open lead in MakonBook</a>'])
    return "\n".join(lines)


def _format_completion_reply(payload: dict) -> str:
    return (
        f"✅ <b>Finished</b> · <b>{_result_summary(payload)}</b>"
        f" · <b>{_format_duration(payload.get('elapsed_minutes'))}</b>"
    )


def _pending_ids(limit: int = 20) -> list[int]:
    close_old_connections()
    now = timezone.now()
    return list(
        PlacementTelegramNotification.objects.filter(
            status__in=[
                PlacementTelegramNotification.STATUS_PENDING,
                PlacementTelegramNotification.STATUS_FAILED,
            ],
            next_attempt_at__lte=now,
        )
        .order_by("created_at")
        .values_list("pk", flat=True)[:limit]
    )


def _destinations() -> tuple[list[str | int], list[int]]:
    close_old_connections()
    return _configured_group_destinations(), _configured_admin_destinations()


def _mark_delivery(notification_id: int, *, success: bool, error: str = ""):
    close_old_connections()
    notice = PlacementTelegramNotification.objects.filter(pk=notification_id).first()
    if not notice:
        return
    notice.attempts += 1
    if success:
        notice.status = PlacementTelegramNotification.STATUS_SENT
        notice.sent_at = timezone.now()
        notice.last_error = error[:4000]
    else:
        notice.status = PlacementTelegramNotification.STATUS_FAILED
        notice.last_error = error[:4000]
        backoff = min(300, max(15, 15 * (2 ** min(notice.attempts, 4))))
        notice.next_attempt_at = timezone.now() + timedelta(seconds=backoff)
    notice.save(
        update_fields=["attempts", "status", "sent_at", "last_error", "next_attempt_at", "updated_at"]
    )


def _is_message_not_modified(exc: Exception) -> bool:
    return "message is not modified" in str(exc).lower()


async def _remember_message(payload: dict, chat_id, field: str, result) -> int | None:
    message_id = _message_id_from_result(result)
    if not message_id or not payload.get("lead_id"):
        return message_id
    await sync_to_async(_store_thread_message_id, thread_sensitive=True)(
        payload["lead_id"], chat_id, field, message_id
    )
    # Keep this in-memory snapshot current for repeated destinations/tests in this run.
    threads = payload.setdefault("telegram_threads", {})
    refs = threads.setdefault(_chat_key(chat_id), {})
    refs[field] = message_id
    return message_id


async def _deliver_notice_to_chat(bot, payload: dict, chat_id: str | int) -> tuple[bool, list[str]]:
    """Deliver one notice to one chat while keeping START/FINISH attached."""
    errors: list[str] = []
    refs = _thread_refs(payload, chat_id)
    kind = payload.get("kind")

    if kind == PlacementTelegramNotification.KIND_STARTED:
        if refs.get(THREAD_START_KEY):
            return True, errors
        try:
            result = await bot.send_message(chat_id=chat_id, text=_format_message(payload))
            await _remember_message(payload, chat_id, THREAD_START_KEY, result)
            return True, errors
        except Exception as exc:
            errors.append(f"start send: {exc}")
            return False, errors

    # Completion is idempotent. If a completion reply/fallback has already been
    # persisted, do not create another message after a worker/container restart.
    if refs.get(THREAD_COMPLETION_KEY):
        return True, errors

    completed_text = _format_message(payload)
    reply_text = _format_completion_reply(payload)
    start_message_id = refs.get(THREAD_START_KEY)

    if start_message_id:
        edited = False
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=int(start_message_id),
                text=completed_text,
            )
            edited = True
        except Exception as exc:
            if _is_message_not_modified(exc):
                edited = True
            else:
                errors.append(f"completion edit: {exc}")

        if edited:
            # Primary UX: edit the original START card, then create a short reply
            # so completion is visible at the bottom of a busy group chat.
            try:
                result = await bot.send_message(
                    chat_id=chat_id,
                    text=reply_text,
                    reply_to_message_id=int(start_message_id),
                    allow_sending_without_reply=False,
                )
                await _remember_message(payload, chat_id, THREAD_COMPLETION_KEY, result)
                return True, errors
            except Exception as exc:
                errors.append(f"completion reply: {exc}")
                # Visibility fallback: the edited card is correct, but Telegram
                # could not create a reply. Send the short completion as a normal
                # message instead so staff still sees the finish event.
                try:
                    result = await bot.send_message(chat_id=chat_id, text=reply_text)
                    await _remember_message(payload, chat_id, THREAD_COMPLETION_KEY, result)
                    return True, errors
                except Exception as fallback_exc:
                    errors.append(f"completion reply fallback: {fallback_exc}")
                    return False, errors

        # The stored START message may have been deleted or become uneditable.
        # Send a full completion card instead; never lose the result.
        try:
            result = await bot.send_message(chat_id=chat_id, text=completed_text)
            await _remember_message(payload, chat_id, THREAD_COMPLETION_KEY, result)
            return True, errors
        except Exception as exc:
            errors.append(f"completion full fallback: {exc}")
            return False, errors

    # Backwards compatibility for attempts whose START was delivered before V5616
    # (there is no stored message_id yet).
    try:
        result = await bot.send_message(chat_id=chat_id, text=completed_text)
        await _remember_message(payload, chat_id, THREAD_COMPLETION_KEY, result)
        return True, errors
    except Exception as exc:
        errors.append(f"completion send: {exc}")
        return False, errors


async def deliver_pending_placement_notifications(bot) -> int:
    ids = await sync_to_async(_pending_ids, thread_sensitive=True)()
    if not ids:
        return 0

    group_destinations, admin_destinations = await sync_to_async(
        _destinations, thread_sensitive=True
    )()
    if not group_destinations and not admin_destinations:
        logger.warning(
            "Public placement notifications are pending but no Telegram recipient is configured."
        )
        return 0

    delivered = 0
    for notification_id in ids:
        payload = await sync_to_async(_notification_snapshot, thread_sensitive=True)(notification_id)
        if not payload:
            continue
        failures: list[str] = []

        # V5615/V5616: an explicitly configured placement group is the PRIMARY route.
        if group_destinations:
            group_successes = 0
            for chat_id in group_destinations:
                ok, errors = await _deliver_notice_to_chat(bot, payload, chat_id)
                if ok:
                    group_successes += 1
                for error in errors:
                    failures.append(f"placement target {chat_id}: {error}")
                    logger.warning(
                        "Placement Telegram group delivery issue for %s: %s", chat_id, error
                    )

            if group_successes == 0:
                await sync_to_async(_mark_delivery, thread_sensitive=True)(
                    notification_id,
                    success=False,
                    error="\n".join(failures),
                )
                # Do not send fallback DMs and accidentally mask a broken explicit route.
                continue

            # Active TelegramAdmin recipients remain optional copies. V5616 threads
            # those copies too when Telegram returns a message_id.
            for chat_id in admin_destinations:
                if chat_id in group_destinations:
                    continue
                ok, errors = await _deliver_notice_to_chat(bot, payload, chat_id)
                for error in errors:
                    failures.append(f"admin copy {chat_id}: {error}")
                    logger.warning(
                        "Placement Telegram admin-copy delivery issue for %s: %s", chat_id, error
                    )
                if not ok and not errors:
                    failures.append(f"admin copy {chat_id}: unknown delivery failure")

            await sync_to_async(_mark_delivery, thread_sensitive=True)(
                notification_id,
                success=True,
                error="\n".join(failures),
            )
            delivered += 1
            continue

        # No explicit placement group: preserve the legacy admin fallback route,
        # now with the same per-attempt threading behavior.
        admin_successes = 0
        for chat_id in admin_destinations:
            ok, errors = await _deliver_notice_to_chat(bot, payload, chat_id)
            if ok:
                admin_successes += 1
            for error in errors:
                failures.append(f"admin {chat_id}: {error}")
                logger.warning(
                    "Placement Telegram admin delivery issue for %s: %s", chat_id, error
                )

        await sync_to_async(_mark_delivery, thread_sensitive=True)(
            notification_id,
            success=admin_successes > 0,
            error="\n".join(failures),
        )
        if admin_successes:
            delivered += 1
    return delivered


async def placement_notification_worker(bot, *, interval_seconds: int = 8):
    logger.info("Public placement Telegram notification worker started.")
    try:
        while True:
            try:
                await deliver_pending_placement_notifications(bot)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Public placement notification worker iteration failed.")
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("Public placement Telegram notification worker stopped.")
        raise

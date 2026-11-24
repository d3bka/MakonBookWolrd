"""V103: who may use the MakonBook Telegram bot.

* Super admins are Telegram user ids in ``TELEGRAM_SUPERADMIN_IDS`` (.env). Nobody can
  become one from the bot or the website.
* Super admins grant and take away access in the bot ("👥 Access") or on the website
  (Admin → Telegram bot access). Everyone with access is an Admin; there is one role.
* Everyone else gets "Access denied" together with their Telegram id, so they can send
  it to a super admin.
"""
from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from .models import TelegramAdmin


def superadmin_ids() -> set[int]:
    ids = set()
    for item in str(getattr(settings, "TELEGRAM_SUPERADMIN_IDS", "") or "").replace(";", ",").split(","):
        item = item.strip()
        if item.lstrip("-").isdigit():
            ids.add(int(item))
    return ids


def is_superadmin(telegram_id) -> bool:
    try:
        return int(telegram_id) in superadmin_ids()
    except (TypeError, ValueError):
        return False


def parse_telegram_id(text) -> int | None:
    value = str(text or "").strip().replace(" ", "")
    if value.isdigit() and 5 <= len(value) <= 15:
        return int(value)
    return None


def display_name(admin: TelegramAdmin) -> str:
    name = " ".join(part for part in (admin.first_name, admin.last_name) if part).strip()
    if admin.username:
        name = f"{name} (@{admin.username})" if name else f"@{admin.username}"
    return name or str(admin.telegram_id)


def access_row(telegram_id: int) -> TelegramAdmin | None:
    """The active row of a person who may use the bot. Super admins always get one."""
    if is_superadmin(telegram_id):
        admin, _ = TelegramAdmin.objects.get_or_create(telegram_id=telegram_id, defaults={"is_admin": True, "is_active": True})
        if not (admin.is_active and admin.is_admin):
            admin.is_active = admin.is_admin = True
            admin.save(update_fields=["is_active", "is_admin"])
        return admin
    admin = TelegramAdmin.objects.filter(telegram_id=telegram_id, is_active=True).first()
    return admin if admin and (admin.is_admin or admin.is_support) else None


def grant_access(telegram_id: int, *, first_name: str = "", last_name: str = "", username: str = "") -> tuple[TelegramAdmin, bool]:
    """Give ``telegram_id`` Admin access. Returns ``(row, changed)``; ``changed`` is False if it already had it."""
    with transaction.atomic():
        admin, created = TelegramAdmin.objects.select_for_update().get_or_create(
            telegram_id=telegram_id,
            defaults={"is_admin": True, "is_active": True, "first_name": first_name[:100] or None,
                      "last_name": last_name[:100] or None, "username": (username or "").lstrip("@")[:100] or None},
        )
        if created:
            return admin, True
        changed = not (admin.is_active and admin.is_admin)
        admin.is_active = admin.is_admin = True
        for field, value in (("first_name", first_name), ("last_name", last_name), ("username", (username or "").lstrip("@"))):
            if value and not getattr(admin, field):
                setattr(admin, field, value[:100])
        admin.save()
        return admin, changed


def revoke_access(telegram_id: int) -> str:
    """Take access away. Returns "removed", "superadmin" (cannot be removed here) or "missing"."""
    if is_superadmin(telegram_id):
        return "superadmin"
    updated = TelegramAdmin.objects.filter(telegram_id=telegram_id, is_active=True).update(is_active=False)
    return "removed" if updated else "missing"


def people_with_access() -> list[dict]:
    """Super admins first, then everyone else with access."""
    supers = superadmin_ids()
    rows = {a.telegram_id: a for a in TelegramAdmin.objects.filter(Q(is_admin=True) | Q(is_support=True), is_active=True)}
    people = []
    for telegram_id in sorted(supers):
        admin = rows.pop(telegram_id, None)
        people.append({"telegram_id": telegram_id, "name": display_name(admin) if admin else "", "superadmin": True, "admin": admin})
    for admin in sorted(rows.values(), key=lambda a: display_name(a).casefold()):
        people.append({"telegram_id": admin.telegram_id, "name": display_name(admin), "superadmin": False, "admin": admin})
    return people


def alert_chat_ids() -> list[str]:
    """Telegram chats for system alerts when MONITORING_TELEGRAM_CHAT_ID is empty: everyone with access."""
    return [str(p["telegram_id"]) for p in people_with_access()]

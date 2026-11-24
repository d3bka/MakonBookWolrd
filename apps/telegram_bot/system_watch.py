"""V102: the Telegram bot's side of the system health watch (see apps.base.system_health)."""
from __future__ import annotations

import asyncio
import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import close_old_connections

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 60


def watch_once() -> list[str]:
    from apps.base.system_health import beat, run_watch

    close_old_connections()
    try:
        if getattr(settings, "SYSTEM_HEALTH_WATCH_ENABLED", False):
            return run_watch("telegram_bot")
        beat("telegram_bot")
        return []
    finally:
        close_old_connections()


async def system_health_watch_worker():
    while True:
        try:
            await sync_to_async(watch_once, thread_sensitive=False)()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - the watch must never stop the bot
            logger.exception("System health watch failed")
        await asyncio.sleep(INTERVAL_SECONDS)

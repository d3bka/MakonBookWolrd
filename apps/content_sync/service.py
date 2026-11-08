"""One sync run: practice tests, then vocabulary, from makonbook-api.

Started every MAKONBOOK_API_SYNC_INTERVAL_MINUTES by Celery Beat
(apps.content_sync.tasks) and by ``manage.py sync_makonbook_api``.
"""

from __future__ import annotations

import contextlib
import logging
import zlib

from django.conf import settings
from django.db import connection
from django.utils import timezone

from .images import ImageMirror, ImageMirrorUnavailable
from .models import ContentSyncState
from .practice import sync_practice
from .source import ApiSource
from .vocabulary import sync_vocabulary

log = logging.getLogger(__name__)

PARTS = ("practice", "vocabulary")
_LOCK_ID = zlib.crc32(b"makonbook-content-sync")


class SyncAlreadyRunning(RuntimeError):
    pass


@contextlib.contextmanager
def _single_run():
    """One run at a time across every container (a PostgreSQL advisory lock)."""
    if connection.vendor != "postgresql":
        yield
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [_LOCK_ID])
        if not cursor.fetchone()[0]:
            raise SyncAlreadyRunning("Another makonbook-api sync is running.")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [_LOCK_ID])


def _state(key: str) -> ContentSyncState:
    state, _ = ContentSyncState.objects.get_or_create(key=key)
    return state


def run_sync(*, parts=PARTS, dry_run: bool = False, force: bool = False, source=None, mirror=None) -> dict:
    source = source or ApiSource()
    if not source.available():
        return {"skipped": "No makonbook_api database is configured (see MAKONBOOK_API_DATABASE_URL)."}
    mirror = mirror or ImageMirror()
    result = {"dry_run": dry_run}
    with _single_run():
        for part in parts:
            if part not in PARTS:
                raise ValueError(f"Unknown part {part!r}; use one of {', '.join(PARTS)}.")
            state = _state(part)
            started = timezone.now()
            try:
                if part == "practice":
                    summary = sync_practice(source.published_tests(), mirror, dry_run=dry_run, force=force).as_dict()
                else:
                    version = source.vocab_deck_version()
                    unchanged = version and version == state.value and not force
                    lists = None if unchanged else source.vocab_lists()
                    words = None if unchanged else source.vocab_words()
                    summary = sync_vocabulary(
                        version, lists, words, mirror, last_version=state.value, dry_run=dry_run, force=force
                    ).as_dict()
            except Exception as exc:  # noqa: BLE001 - recorded, reported, and the next part still runs
                if isinstance(exc, ImageMirrorUnavailable):
                    log.error("makonbook-api sync of %s failed: %s", part, exc)
                else:
                    log.exception("makonbook-api sync of %s failed", part)
                result[part] = {"error": f"{type(exc).__name__}: {exc}"}
                if not dry_run:
                    state.last_run_at = started
                    state.last_error = result[part]["error"][:4000]
                    state.save(update_fields=["last_run_at", "last_error"])
                continue
            result[part] = summary
            if not dry_run:
                state.last_run_at = started
                failed = summary.get("failed") or {}
                state.last_error = "; ".join(f"{k}: {v}" for k, v in failed.items())[:4000]
                if not failed:
                    state.last_success_at = timezone.now()
                if part == "vocabulary" and not summary.get("skipped"):
                    state.value = summary.get("version") or state.value
                state.last_summary = summary
                state.save()
    if mirror.copied:
        result["images_copied"] = mirror.copied
    return result


def sync_enabled() -> bool:
    return bool(getattr(settings, "MAKONBOOK_API_SYNC_ENABLED", False)) and ApiSource().available()

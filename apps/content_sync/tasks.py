import logging

from celery import shared_task

from .service import SyncAlreadyRunning, run_sync, sync_enabled

log = logging.getLogger(__name__)


@shared_task(name="apps.content_sync.tasks.sync_makonbook_api_content", ignore_result=True, soft_time_limit=30 * 60, time_limit=35 * 60)
def sync_makonbook_api_content():
    """Celery Beat: copy newly published tests and vocabulary from makonbook-api."""
    if not sync_enabled():
        return {"skipped": "disabled"}
    try:
        result = run_sync()
    except SyncAlreadyRunning:
        return {"skipped": "already running"}
    log.info("makonbook-api content sync: %s", result)
    return result

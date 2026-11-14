"""V50.7 World events: hourly settlement (idempotent) and the seasonal cup."""
from celery import shared_task
from django.conf import settings


@shared_task(soft_time_limit=240, time_limit=300)
def settle_world_events():
    from django.utils import timezone

    from .events import ensure_seasonal_competition, settle
    from .models import WorldEvent

    now = timezone.now()
    settled = [settle(e, now) for e in WorldEvent.objects.filter(settled_at__isnull=True, ends_at__lte=now)]
    if getattr(settings, "MAKONBOOK_WORLD_ENABLED", False):
        ensure_seasonal_competition()  # cups only appear once World is open
    return len(settled)

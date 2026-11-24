from celery import shared_task


@shared_task(name="apps.base.tasks.system_heartbeat", ignore_result=True)
def system_heartbeat():
    """V102: Beat schedules this every minute; running it proves Beat and the worker are alive."""
    from apps.base.system_health import beat

    beat("celery", worker=system_heartbeat.request.hostname or "")

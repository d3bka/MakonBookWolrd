"""Deploy-time warnings for data the product cannot run without.

Tagged ``database`` so they only query the DB when Django asks for database
checks — ``manage.py migrate`` (run by entrypoint.sh on every deploy) and
``manage.py check --database default`` — never on every request or import.
"""
from django.core.checks import Tags, Warning, register
from django.utils import timezone


@register(Tags.database)
def upcoming_official_sat_dates(app_configs=None, databases=None, **kwargs):
    if not databases:
        return []
    from .models import OfficialSatDate

    try:
        upcoming = OfficialSatDate.objects.filter(
            is_active=True, date__gte=timezone.localdate()
        ).order_by("date")
        confirmed = upcoming.filter(is_confirmed=True).count()
        total = upcoming.count()
    except Exception:  # table not migrated yet
        return []
    if confirmed >= 2:
        return []
    return [
        Warning(
            f"Only {confirmed} confirmed upcoming SAT date(s) ({total} including provisional).",
            hint="Add or confirm College Board dates in Django admin → Official SAT dates, "
                 "otherwise students cannot pick an exam date for their goal.",
            id="sat.W001",
        )
    ]

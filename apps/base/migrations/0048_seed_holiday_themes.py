"""V85: holiday calendar 2026-2030.

Fixed holidays repeat every year. Ramazon and Qurbon Hayit move with the lunar calendar:
the dates below are astronomical estimates (±1 day). A manager corrects them in the admin
(Base › Holiday themes) once the official date is announced.
"""
from datetime import date

from django.db import migrations

YEARS = range(2026, 2031)
FIXED = (
    ("navruz", (3, 14), (3, 28)),
    ("womens-day", (3, 6), (3, 9)),
    ("independence", (8, 30), (9, 2)),
    ("teachers-day", (9, 30), (10, 2)),
    ("constitution", (12, 7), (12, 9)),
)
# Eid al-Fitr / Eid al-Adha first day (estimate). Decor: the day before -> 2 days after.
RAMAZON = {2026: (3, 20), 2027: (3, 10), 2028: (2, 27), 2029: (2, 15), 2030: (2, 5)}
QURBON = {2026: (5, 27), 2027: (5, 17), 2028: (5, 5), 2029: (4, 24), 2030: (4, 13)}


def seed(apps, schema_editor):
    from datetime import timedelta

    Holiday = apps.get_model("base", "HolidayTheme")
    if Holiday.objects.exists():
        return
    rows = []
    for year in YEARS:
        for key, start, end in FIXED:
            rows.append(Holiday(key=key, start_date=date(year, *start), end_date=date(year, *end)))
        # New Year: 25 December -> 3 January of the next year.
        rows.append(Holiday(key="new-year", start_date=date(year, 12, 25), end_date=date(year + 1, 1, 3)))
        for key, table in (("ramazon-hayit", RAMAZON), ("qurbon-hayit", QURBON)):
            day = date(year, *table[year])
            rows.append(Holiday(key=key, start_date=day - timedelta(days=1), end_date=day + timedelta(days=2),
                                note="Estimated date: confirm when officially announced."))
    rows.append(Holiday(key="new-year", start_date=date(2026, 1, 1), end_date=date(2026, 1, 3)))
    Holiday.objects.bulk_create(rows)


class Migration(migrations.Migration):
    dependencies = [("base", "0047_holiday_themes")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

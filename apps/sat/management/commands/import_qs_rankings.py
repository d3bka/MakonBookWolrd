"""Import an official QS World University Rankings export into the university catalogue.

Download the table from topuniversities.com (free account → Download, CSV or
XLSX). Columns are matched by header name (case-insensitive):
    rank        "1", "=8", "601-610", "1201-1400"
    name        institution name  (also: "institution", "university")
    country     country/territory (also: "location", "country/territory")
    city        optional

Dry run by default:
    python manage.py import_qs_rankings qs_2027.xlsx --year 2027
    python manage.py import_qs_rankings qs_2027.xlsx --year 2027 --max-rank 500 --apply

Existing universities are matched by normalised name (+country) and get their
rank refreshed; new ones are added up to --max-rank. Nothing is deleted;
universities that fell out of the range keep their row but lose the rank only
with --clear-missing.
"""
import csv
import re
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.sat.models import DreamUniversity

HEADER_ALIASES = {
    "rank": ("rank", "2027 rank", "qs rank", "rank display"),
    "name": ("name", "institution", "institution name", "university"),
    "country": ("country", "location", "country/territory", "country / territory"),
    "city": ("city",),
}
_RANK = re.compile(r"^=?\s*(\d+)(?:\s*[-–]\s*(\d+))?\+?$")
_STOP = re.compile(r"\b(the|university|college|of|and)\b")


def normalise(name):
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", _STOP.sub("", text))


def parse_rank(raw):
    """Return (lower_bound, display) or (None, '') for unranked rows."""
    text = str(raw or "").strip()
    match = _RANK.match(text)
    if not match:
        return None, ""
    return int(match.group(1)), text


def read_rows(path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            yield from csv.DictReader(handle)
    elif suffix in {".xlsx", ".xlsm"}:
        from openpyxl import load_workbook

        sheet = load_workbook(path, read_only=True, data_only=True).active
        rows = sheet.iter_rows(values_only=True)
        header = None
        for row in rows:
            cells = [str(c or "").strip() for c in row]
            if header is None:
                if any(c.lower() in HEADER_ALIASES["rank"] for c in cells):
                    header = cells
                continue
            yield dict(zip(header, row))
    else:
        raise CommandError("Use a .csv or .xlsx QS export.")


def pick(row, field):
    lowered = {str(k or "").strip().lower(): v for k, v in row.items()}
    for alias in HEADER_ALIASES[field]:
        if alias in lowered and lowered[alias] not in (None, ""):
            return str(lowered[alias]).strip()
    return ""


class Command(BaseCommand):
    help = "Import an official QS rankings CSV/XLSX into DreamUniversity (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--year", type=int, required=True, help="QS edition year, e.g. 2027.")
        parser.add_argument("--max-rank", type=int, default=500, help="Add new universities up to this rank.")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--clear-missing", action="store_true",
                            help="Remove the rank from catalogue rows not present in this export.")

    def handle(self, path, year, max_rank, apply, clear_missing, **options):
        source = Path(path)
        if not source.exists():
            raise CommandError(f"File not found: {source}")

        existing = {}
        for uni in DreamUniversity.objects.all():
            existing.setdefault(normalise(uni.name), []).append(uni)

        updated = created = skipped = 0
        seen_ids = set()
        plan = []
        for row in read_rows(source):
            name, country, city = pick(row, "name"), pick(row, "country"), pick(row, "city")
            rank, display = parse_rank(pick(row, "rank"))
            if not name or rank is None:
                skipped += 1
                continue
            matches = existing.get(normalise(name), [])
            match = next((u for u in matches if not country or u.country.lower() == country.lower()), None) or (
                matches[0] if len(matches) == 1 else None
            )
            note = f"QS World University Rankings {year}: #{display.lstrip('=') if '-' in display else display}."
            if match:
                seen_ids.add(match.pk)
                if match.qs_rank != rank or match.ranking_year != year:
                    plan.append(("update", match, rank, note))
                    updated += 1
            elif rank <= max_rank:
                plan.append(("create", (name[:180], country[:120], city[:120]), rank, note))
                created += 1

        cleared = 0
        if clear_missing:
            stale = DreamUniversity.objects.exclude(pk__in=seen_ids).filter(qs_rank__isnull=False)
            cleared = stale.count()

        for action, target, rank, note in plan[:25]:
            label = target.name if action == "update" else target[0]
            self.stdout.write(f"{action:6} #{rank:<5} {label}")
        if len(plan) > 25:
            self.stdout.write(f"... and {len(plan) - 25} more")

        if apply:
            with transaction.atomic():
                for action, target, rank, note in plan:
                    fields = {"qs_rank": rank, "ranking_year": year,
                              "ranking_source": "QS World University Rankings", "sort_order": rank}
                    if action == "update":
                        DreamUniversity.objects.filter(pk=target.pk).update(**fields)
                    else:
                        name, country, city = target
                        DreamUniversity.objects.update_or_create(
                            name=name, country=country,
                            defaults={**fields, "city": city, "score_note": note[:180], "is_active": True},
                        )
                if clear_missing:
                    DreamUniversity.objects.exclude(pk__in=seen_ids).filter(qs_rank__isnull=False).update(
                        qs_rank=None, ranking_year=None)

        verb = "Applied" if apply else "Would apply"
        self.stdout.write(self.style.SUCCESS(
            f"{verb}: {updated} rank update(s), {created} new universit(ies) up to #{max_rank}"
            + (f", {cleared} rank(s) cleared" if clear_missing else "")
            + f"; {skipped} row(s) without a usable rank/name skipped."
            + ("" if apply else " Dry run — re-run with --apply.")
        ))

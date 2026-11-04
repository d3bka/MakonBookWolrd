import json

from django.core.management.base import BaseCommand, CommandError

from apps.content_sync.service import PARTS, SyncAlreadyRunning, run_sync


class Command(BaseCommand):
    help = (
        "Copy published practice tests and vocabulary from makonbook-api's database "
        "(read only) into this site. Celery Beat runs the same sync every few minutes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would change; write nothing.")
        parser.add_argument("--force", action="store_true", help="Rewrite every test and word even if unchanged.")
        parser.add_argument("--only", choices=PARTS, help="Sync one part only.")

    def handle(self, *args, **options):
        parts = (options["only"],) if options["only"] else PARTS
        try:
            result = run_sync(parts=parts, dry_run=options["dry_run"], force=options["force"])
        except SyncAlreadyRunning as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        conflicts = (result.get("practice") or {}).get("conflicts") or []
        if conflicts:
            self.stderr.write(self.style.WARNING(
                f"Not synced, because a test made in this app has the same name: {', '.join(conflicts)}. "
                "Run `python manage.py remove_legacy_tests` (then with --confirm) first; a test an event "
                "runs on stays until the event uses another test."
            ))
        if "skipped" in result:
            raise CommandError(result["skipped"])
        errors = [p for p in parts if isinstance(result.get(p), dict) and (result[p].get("error") or result[p].get("failed"))]
        if errors:
            raise CommandError(f"Sync finished with errors in: {', '.join(errors)}")

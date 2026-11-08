from django.core.management.base import BaseCommand

from apps.content_sync.legacy import remove_legacy_tests


class Command(BaseCommand):
    help = (
        "Remove the regular practice tests made in this app (not synced from makonbook-api) with "
        "their questions and results. Placement, event and makeup tests stay. Shows what it would "
        "delete unless --confirm."
    )

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Really delete. Without it nothing changes.")

    def handle(self, *args, **options):
        result = remove_legacy_tests(confirm=options["confirm"])
        tests = result["tests"]
        verb = "Deleted" if result["confirmed"] else "Would delete"
        self.stdout.write(f"{verb} {len(tests)} test(s): {', '.join(map(str, tests[:80]))}{' …' if len(tests) > 80 else ''}")
        for label, n in result["deleted"].items():
            self.stdout.write(f"  {label}: {n}")
        for test, events in result["kept_for_events"].items():
            self.stdout.write(self.style.WARNING(
                f"Kept {test}: the event(s) {', '.join(events)} run on it. The synced test of the same "
                "name can't be created until the event is moved to another test or removed."
            ))
        if not result["confirmed"]:
            self.stdout.write(self.style.WARNING("Nothing was deleted. Run again with --confirm to delete."))
        else:
            self.stdout.write(self.style.SUCCESS("Done."))

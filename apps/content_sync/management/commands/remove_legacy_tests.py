from django.core.management.base import BaseCommand

from apps.content_sync.legacy import remove_legacy_tests


class Command(BaseCommand):
    help = (
        "Remove every test not synced from makonbook-api (regular, placement, event and makeup "
        "tests) with its questions and results. Shows what it would delete unless --confirm."
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
        if not result["confirmed"]:
            self.stdout.write(self.style.WARNING("Nothing was deleted. Run again with --confirm to delete."))
        else:
            self.stdout.write(self.style.SUCCESS("Done."))

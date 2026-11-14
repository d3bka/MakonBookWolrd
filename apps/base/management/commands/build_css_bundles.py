from django.core.management.base import BaseCommand

from apps.base.css_bundles import BUNDLES, CSS_DIR, render_bundle


class Command(BaseCommand):
    help = "Regenerate the student shell CSS bundles from their source files."

    def handle(self, *args, **options):
        for name in BUNDLES:
            content = render_bundle(name)
            target = CSS_DIR / name
            previous = target.read_text(encoding="utf-8") if target.exists() else None
            target.write_text(content, encoding="utf-8", newline="\n")
            state = "unchanged" if previous == content else "written"
            self.stdout.write(f"{state:9} {name} ({len(BUNDLES[name])} files, {len(content) // 1024} KB)")

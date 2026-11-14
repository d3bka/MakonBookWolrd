"""Move already-uploaded student/exam files to unguessable storage keys.

New uploads get random keys automatically (apps.base.upload_paths). Files
uploaded before that keep guessable names like ``classroom_chat_files/IMG_1234.jpg``
on the public bucket domain. This command copies each such file to a random
key, points the database row at the copy, and only then deletes the old object.

Dry run by default:
    python manage.py randomize_upload_keys            # report only
    python manage.py randomize_upload_keys --apply    # copy, repoint, delete old
    python manage.py randomize_upload_keys --apply --keep-old   # do not delete old keys
"""
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.base.upload_paths import is_random_name

TARGETS = (
    ("apclasses", "APFRQSubmission", "image"),
    ("apclasses", "APFRQSubmission", "file"),
    ("apclasses", "APFRQPage", "image"),
    ("apclasses", "APFRQPage", "file"),
    ("sat", "ChatMessage", "file"),
    ("sat", "ClassroomLessonResource", "file"),
    ("base", "GeneralIssueReport", "attachment"),
)


class Command(BaseCommand):
    help = "Copy existing sensitive uploads to random storage keys (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Actually copy files and update rows.")
        parser.add_argument("--keep-old", action="store_true", help="Do not delete the old objects after copying.")
        parser.add_argument("--limit", type=int, default=0, help="Stop after this many files (0 = no limit).")

    def handle(self, *args, apply=False, keep_old=False, limit=0, **options):
        moved = skipped = failed = 0
        for app_label, model_name, field_name in TARGETS:
            model = apps.get_model(app_label, model_name)
            field = model._meta.get_field(field_name)
            rows = model.objects.exclude(**{field_name: ""}).exclude(**{f"{field_name}__isnull": True})
            for row in rows.iterator():
                if limit and moved >= limit:
                    break
                current = getattr(row, field_name)
                old_name = current.name
                if is_random_name(old_name):
                    skipped += 1
                    continue
                if not apply:
                    moved += 1
                    self.stdout.write(f"would move {app_label}.{model_name}#{row.pk}.{field_name}: {old_name}")
                    continue
                try:
                    new_name = field.generate_filename(row, old_name.rsplit("/", 1)[-1])
                    with field.storage.open(old_name, "rb") as source:
                        new_name = field.storage.save(new_name, source)
                    updates = {field_name: new_name}
                    if model_name == "ChatMessage" and not row.file_original_name:
                        updates["file_original_name"] = old_name.rsplit("/", 1)[-1][:255]
                    with transaction.atomic():
                        model.objects.filter(pk=row.pk).update(**updates)
                    if not keep_old:
                        field.storage.delete(old_name)
                    moved += 1
                    self.stdout.write(f"moved {app_label}.{model_name}#{row.pk}.{field_name}")
                except Exception as exc:  # keep going; report every failure
                    failed += 1
                    self.stderr.write(f"FAILED {app_label}.{model_name}#{row.pk}.{field_name}: {type(exc).__name__}")
        verb = "Moved" if apply else "Would move"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {moved} file(s); {skipped} already random; {failed} failed."
            + ("" if apply else " Dry run — re-run with --apply.")
        ))

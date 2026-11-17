"""V81: turn SATMakon's "Lessons" folder into protected Admissions content.

    manage.py import_admissions_media /premium/incoming/Lessons
    manage.py import_admissions_media /premium/incoming/Lessons --only 3 --force
    manage.py import_admissions_media /premium/incoming/Lessons --docs-only

* "Lesson <N> - <title>.mp4" -> AES-128 encrypted HLS for the lesson with order N.
  V82: when the private R2 bucket is configured (MAKONBOOK_PREMIUM_R2_*), the encrypted
  segments are uploaded there and removed from the server (use --keep-on-server to skip).
* PDFs listed in apps/sat/admissions_course.py DOCUMENTS -> page images.
Everything is written to settings.MAKONBOOK_PREMIUM_ROOT. The source folder is only read;
delete it from the server once the import has finished (see docs/ADMISSIONS_PREMIUM.md).
"""
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.sat import admissions_media as media
from apps.sat.admissions_course import DOCUMENTS, load_admissions_documents
from apps.sat.models import AdmissionsDocument, AdmissionsLesson, AdmissionsVideo

VIDEO_FILE = re.compile(r"^Lesson\s+(\d+)\s*-\s*.+\.mp4$", re.IGNORECASE)


class Command(BaseCommand):
    help = "Import premium Admissions videos (encrypted HLS) and PDFs (page images) from a folder."

    def add_arguments(self, parser):
        parser.add_argument("source", help="Folder with 'Lesson N - ....mp4' files and the PDFs.")
        parser.add_argument("--force", action="store_true", help="Re-import items that already exist.")
        parser.add_argument("--only", type=int, action="append", default=[], help="Only this lesson number (repeatable).")
        parser.add_argument("--videos-only", action="store_true")
        parser.add_argument("--docs-only", action="store_true")
        parser.add_argument("--keep-on-server", action="store_true",
                            help="Keep segments on the server volume even when the private R2 bucket is set.")
        parser.add_argument("--reencode", action="store_true",
                            help="Re-encode to H.264/AAC instead of copying streams (slow; only for odd sources).")

    def handle(self, *args, **options):
        source = Path(options["source"]).expanduser()
        if not source.is_dir():
            raise CommandError(f"Folder not found: {source}")
        root = media.premium_root()
        root.mkdir(parents=True, exist_ok=True)
        if self._inside_public_folder(root):
            raise CommandError(f"MAKONBOOK_PREMIUM_ROOT ({root}) is inside a public folder. Refusing to write there.")
        self.stdout.write(f"Premium folder: {root}")
        self.use_r2 = media.r2_configured() and not options["keep_on_server"]
        if self.use_r2:
            bucket = media.assert_private_bucket()
            self.stdout.write(f"Encrypted segments go to the private R2 bucket: {bucket}")
        if not options["docs_only"]:
            self._videos(source, options)
        if not options["videos_only"]:
            self._documents(source, options)

    @staticmethod
    def _inside_public_folder(root):
        from django.conf import settings

        root = root.resolve()
        public = [Path(settings.MEDIA_ROOT), Path(getattr(settings, "STATIC_ROOT", "") or "/nonexistent")]
        public += [Path(p) for p in getattr(settings, "STATICFILES_DIRS", [])]
        return any(root == p.resolve() or p.resolve() in root.parents for p in public if str(p))

    def _videos(self, source, options):
        files = sorted((p for p in source.iterdir() if p.is_file() and VIDEO_FILE.match(p.name)),
                       key=lambda p: int(VIDEO_FILE.match(p.name).group(1)))
        if not files:
            self.stdout.write(self.style.WARNING("No 'Lesson N - ....mp4' files found."))
        for path in files:
            number = int(VIDEO_FILE.match(path.name).group(1))
            if options["only"] and number not in options["only"]:
                continue
            lesson = AdmissionsLesson.objects.filter(order=number).order_by("id").first()
            if lesson is None:
                self.stdout.write(self.style.WARNING(f"  #{number}: no lesson with order {number}, skipped"))
                continue
            existing = AdmissionsVideo.objects.filter(lesson=lesson).first()
            if existing and not options["force"]:
                self.stdout.write(f"  #{number} {lesson.title}: already imported")
                continue
            self.stdout.write(f"  #{number} {lesson.title}: encrypting {path.name} ...")
            result = media.encrypt_video_to_hls(path, reencode=options["reencode"])
            playlist = (media.video_dir(result["asset"]) / "index.m3u8").read_text(encoding="utf-8")
            storage = AdmissionsVideo.STORAGE_LOCAL
            if self.use_r2:
                uploaded = media.upload_video_to_r2(result["asset"])
                storage = AdmissionsVideo.STORAGE_R2
                self.stdout.write(f"     uploaded {uploaded} encrypted segments to R2")
            old = (existing.asset, existing.storage) if existing else None
            with transaction.atomic():
                AdmissionsVideo.objects.update_or_create(lesson=lesson, defaults={
                    "asset": result["asset"], "key_hex": result["key_hex"],
                    "duration_seconds": result["duration_seconds"], "segment_count": result["segment_count"],
                    "source_name": path.name, "storage": storage, "playlist_text": playlist,
                })
                if result["duration_seconds"]:
                    lesson.minutes = max(1, round(result["duration_seconds"] / 60))
                    lesson.save(update_fields=["minutes"])
            if storage == AdmissionsVideo.STORAGE_R2:
                media.remove_asset(media.video_dir(result["asset"]))  # the bytes now live only in R2
            if old:
                media.remove_asset(media.video_dir(old[0]))
                if old[1] == AdmissionsVideo.STORAGE_R2:
                    media.delete_video_from_r2(old[0])
            self.stdout.write(self.style.SUCCESS(
                f"     done: {result['segment_count']} encrypted segments, {result['duration_seconds'] // 60} min"))

    def _documents(self, source, options):
        load_admissions_documents(AdmissionsDocument, AdmissionsLesson)
        by_name = {p.name.lower(): p for p in source.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"}
        for data in DOCUMENTS:
            document = AdmissionsDocument.objects.filter(slug=data["slug"]).first()
            if document is None:
                continue
            path = by_name.get((document.source_name or data["source"]).lower())
            if path is None:
                self.stdout.write(self.style.WARNING(f"  {document.title}: {document.source_name} not found"))
                continue
            if document.is_ready and not options["force"]:
                self.stdout.write(f"  {document.title}: already imported")
                continue
            old_asset = document.asset
            asset, pages = media.render_pdf_pages(path)
            document.asset, document.page_count = asset, pages
            document.save(update_fields=["asset", "page_count"])
            if old_asset:
                media.remove_asset(media.doc_dir(old_asset))
            self.stdout.write(self.style.SUCCESS(f"  {document.title}: {pages} pages"))

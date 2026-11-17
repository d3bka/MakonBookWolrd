"""V82: move already imported premium videos from the server volume to the private R2 bucket.

    manage.py push_admissions_media_to_r2 --check      # settings and bucket only, nothing uploaded
    manage.py push_admissions_media_to_r2 --cors       # allow GET from the site's own origins
    manage.py push_admissions_media_to_r2              # upload, verify, switch, delete local copies

Only the encrypted segments go to R2. Keys and playlists stay in the database.
V86: PDF page images move too (the PDF itself never existed on the server). The site
stamps the viewer's watermark on each page after reading it from the private bucket.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.sat import admissions_media as media
from apps.sat.models import AdmissionsDocument, AdmissionsVideo


class Command(BaseCommand):
    help = "Upload encrypted Admissions video segments to the private R2 bucket."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true", help="Only check settings and bucket access.")
        parser.add_argument("--cors", action="store_true", help="Set the bucket CORS rule for the site's origins.")
        parser.add_argument("--keep-local", action="store_true", help="Do not delete the server copies.")

    def handle(self, *args, **options):
        if not media.r2_configured():
            raise CommandError("Set MAKONBOOK_PREMIUM_R2_BUCKET, _ENDPOINT_URL, _ACCESS_KEY_ID and _SECRET_ACCESS_KEY first.")
        try:
            bucket = media.assert_private_bucket()
        except RuntimeError as error:
            raise CommandError(str(error)) from error
        client = media.r2_client()
        try:
            client.head_bucket(Bucket=bucket)
        except Exception as error:  # noqa: BLE001
            raise CommandError(f"Cannot reach the bucket {bucket}: {error.__class__.__name__}") from error
        self.stdout.write(f"Private bucket OK: {bucket}")
        if options["cors"] or options["check"]:
            if options["cors"]:
                origins = media.apply_bucket_cors()
                self.stdout.write(self.style.SUCCESS(f"CORS: GET allowed only from {', '.join(origins)}"))
            if options["check"]:
                self.stdout.write(f"Presigned links live {settings.MAKONBOOK_PREMIUM_R2_URL_TTL} s.")
                return
        moved = 0
        for video in AdmissionsVideo.objects.filter(storage=AdmissionsVideo.STORAGE_LOCAL).select_related("lesson"):
            folder = media.video_dir(video.asset)
            if not folder.is_dir():
                self.stdout.write(self.style.WARNING(f"  {video.lesson}: no local folder, skipped"))
                continue
            if not video.playlist_text and (folder / "index.m3u8").is_file():
                video.playlist_text = (folder / "index.m3u8").read_text(encoding="utf-8")
            count = media.upload_video_to_r2(video.asset)
            video.storage = AdmissionsVideo.STORAGE_R2
            video.save(update_fields=["storage", "playlist_text", "updated_at"])
            if not options["keep_local"]:
                media.remove_asset(folder)
            moved += 1
            self.stdout.write(self.style.SUCCESS(f"  {video.lesson}: {count} segments in R2"))
        files = 0
        for document in AdmissionsDocument.objects.filter(storage=AdmissionsVideo.STORAGE_LOCAL).exclude(asset=""):
            folder = media.doc_dir(document.asset)
            if not folder.is_dir():
                self.stdout.write(self.style.WARNING(f"  {document.title}: no local folder, skipped"))
                continue
            count = media.upload_doc_to_r2(document.asset)
            document.storage = AdmissionsVideo.STORAGE_R2
            document.save(update_fields=["storage"])
            if not options["keep_local"]:
                media.remove_asset(folder)
            files += 1
            self.stdout.write(self.style.SUCCESS(f"  {document.title}: {count} pages in R2"))
        self.stdout.write(self.style.SUCCESS(f"Done: {moved} video(s) and {files} file(s) moved to R2."))

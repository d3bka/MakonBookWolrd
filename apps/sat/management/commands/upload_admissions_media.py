"""V86: upload premium Admissions lessons from your own PC. Nothing goes through the server.

    python manage.py upload_admissions_media "C:/Users/me/Desktop/Lessons" --dry-run
    python manage.py upload_admissions_media "C:/Users/me/Desktop/Lessons"
    python manage.py upload_admissions_media "C:/Users/me/Desktop/Lessons" --only 7 --force

For every "Lesson <N> - <title>.mp4" the PC:
  1. encrypts the video into AES-128 HLS in a temporary folder (ffmpeg; on Windows
     `pip install imageio-ffmpeg` is enough),
  2. uploads only the encrypted segments to the PRIVATE R2 bucket,
  3. sends the site the lesson number, the key and the playlist over HTTPS
     (POST /api/admissions-media/video/ with MAKONBOOK_MEDIA_UPLOAD_TOKEN),
  4. deletes the temporary folder. The mp4 on your PC is only read.
PDFs named in apps/sat/admissions_course.py DOCUMENTS become page images that go to the
same private bucket; the site stamps the viewer's watermark on every page it shows.

The PC's .env needs the MAKONBOOK_PREMIUM_R2_* values (the same private bucket as the site)
and MAKONBOOK_MEDIA_UPLOAD_TOKEN (the same value as on the site).
"""
import json
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.sat import admissions_media as media

VIDEO_FILE = re.compile(r"^Lesson\s+(\d+)\s*-\s*.+\.mp4$", re.IGNORECASE)
LOCAL_HOSTS = {"localhost", "127.0.0.1"}


class ApiError(Exception):
    def __init__(self, message, answered=True):
        super().__init__(message)
        # False when the site may have saved the record but the answer was lost.
        self.answered = answered


def _may_clean_up(error, posted):
    """Remove an upload from R2 only when the site surely did not register it."""
    return not posted or (isinstance(error, ApiError) and error.answered)


class Command(BaseCommand):
    help = "Encrypt Admissions videos and PDFs on this PC, upload them to the private R2 bucket and register them on the site."

    def add_arguments(self, parser):
        parser.add_argument("source", help="Folder with 'Lesson N - ....mp4' files and the PDFs.")
        parser.add_argument("--site", default="", help="Site address (default MAKONBOOK_MEDIA_UPLOAD_SITE).")
        parser.add_argument("--only", type=int, action="append", default=[], help="Only this lesson number (repeatable).")
        parser.add_argument("--force", action="store_true", help="Replace what the site already has.")
        parser.add_argument("--videos-only", action="store_true")
        parser.add_argument("--docs-only", action="store_true")
        parser.add_argument("--reencode", action="store_true",
                            help="Re-encode to H.264/AAC instead of copying streams (slow; only for odd sources).")
        parser.add_argument("--dry-run", action="store_true", help="Only show what would be uploaded.")

    # ------------------------------------------------------------------ setup

    def handle(self, *args, **options):
        source = Path(options["source"]).expanduser()
        if not source.is_dir():
            raise CommandError(f"Folder not found: {source}")
        self.token = getattr(settings, "MAKONBOOK_MEDIA_UPLOAD_TOKEN", "") or ""
        if len(self.token) < 32:
            raise CommandError("Set MAKONBOOK_MEDIA_UPLOAD_TOKEN in .env (the same long value as on the site).")
        self.site = (options["site"] or settings.MAKONBOOK_MEDIA_UPLOAD_SITE).rstrip("/")
        parsed = urlparse(self.site)
        if parsed.scheme != "https" and parsed.hostname not in LOCAL_HOSTS:
            raise CommandError(f"The site must be https:// ({self.site}). The key travels in this request.")
        if not media.r2_configured():
            raise CommandError("Set MAKONBOOK_PREMIUM_R2_BUCKET, _ENDPOINT_URL, _ACCESS_KEY_ID and _SECRET_ACCESS_KEY in .env.")
        try:
            bucket = media.assert_private_bucket()
        except RuntimeError as error:
            raise CommandError(str(error)) from error

        state = self.call("GET", "status/")
        if state.get("bucket") != bucket:
            raise CommandError(f"This PC uploads to the bucket '{bucket}', but the site reads '{state.get('bucket')}'.")
        self.stdout.write(f"Site: {self.site} · private bucket: {bucket}")
        self.lessons = {item["order"]: item for item in state.get("lessons", [])}
        self.documents = state.get("documents", [])
        self.options = options
        self.failures = 0

        do_videos, do_docs = not options["docs_only"], not options["videos_only"]
        if do_videos and not options["dry_run"]:
            self._check_ffmpeg()
        with tempfile.TemporaryDirectory(prefix="makonbook-upload-") as work:
            if do_videos:
                self._videos(source, Path(work))
            if do_docs:
                self._documents(source, Path(work))
        if self.failures:
            raise CommandError(f"{self.failures} item(s) failed; see above. Run the same command again to retry them.")
        self.stdout.write(self.style.SUCCESS("Done."))

    def _check_ffmpeg(self):
        binary = media.ffmpeg_binary()
        try:
            subprocess.run([binary, "-version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            raise CommandError("ffmpeg was not found. Install it, or run: pip install imageio-ffmpeg") from error

    # ------------------------------------------------------------------ site API

    def call(self, method, path, payload=None):
        try:
            return self.transport(method, path, payload)
        except ApiError as error:
            raise CommandError(f"The site answered: {error}") from error

    def transport(self, method, path, payload=None):
        """One request to the site's media API (tests replace this)."""
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self.site}/api/admissions-media/{path}", data=body, method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
                     "Accept": "application/json", "User-Agent": "MakonBook-media-uploader/86"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            try:
                message = json.loads(error.read().decode("utf-8")).get("error", "")
            except ValueError:
                message = ""
            raise ApiError(f"HTTP {error.code} {message}".strip()) from error
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise ApiError(f"cannot reach {self.site}: {error}", answered=False) from error

    # ------------------------------------------------------------------ videos

    def _videos(self, source, work):
        files = sorted((p for p in source.iterdir() if p.is_file() and VIDEO_FILE.match(p.name)),
                       key=lambda p: int(VIDEO_FILE.match(p.name).group(1)))
        if not files:
            self.stdout.write(self.style.WARNING("No 'Lesson N - ....mp4' files found."))
        for path in files:
            number = int(VIDEO_FILE.match(path.name).group(1))
            if self.options["only"] and number not in self.options["only"]:
                continue
            lesson = self.lessons.get(number)
            if lesson is None:
                self.stdout.write(self.style.WARNING(f"  #{number}: the site has no lesson {number}, skipped"))
                continue
            current = lesson.get("video")
            if current and not self.options["force"]:
                same = current.get("source_name") == path.name
                self.stdout.write(f"  #{number} {lesson['title']}: " + (
                    "already on the site" if same else
                    f"the site already has {current.get('source_name') or 'a video'}; add --force --only {number} to replace"))
                continue
            size = path.stat().st_size / (1024 * 1024)
            if self.options["dry_run"]:
                self.stdout.write(f"  #{number} {lesson['title']}: would upload {path.name} ({size:.0f} MB)")
                continue
            self._upload_video(number, lesson, path, work, size)

    def _upload_video(self, number, lesson, path, work, size):
        self.stdout.write(f"  #{number} {lesson['title']}: encrypting {path.name} ({size:.0f} MB) ...")
        started = time.monotonic()
        try:
            result = media.encrypt_video_to_hls(path, reencode=self.options["reencode"], root=work)
        except Exception as error:  # noqa: BLE001 - report and continue with the next lesson
            self.failures += 1
            self.stdout.write(self.style.ERROR(f"     encrypting failed: {str(error)[:300]}"))
            return
        folder = media.local_asset_dir(work, media.VIDEO_DIR, result["asset"])
        posted = False
        try:
            playlist = (folder / "index.m3u8").read_text(encoding="utf-8")
            self.stdout.write(f"     uploading {result['segment_count']} encrypted segments to R2 ...")
            media.upload_video_to_r2(result["asset"], folder=folder)
            posted = True
            answer = self.transport("POST", "video/", {
                "lesson_order": number, "asset": result["asset"], "key_hex": result["key_hex"],
                "playlist_text": playlist, "duration_seconds": result["duration_seconds"],
                "segment_count": result["segment_count"], "source_name": path.name,
            })
        except Exception as error:  # noqa: BLE001
            self.failures += 1
            self.stdout.write(self.style.ERROR(f"     failed: {str(error)[:300]}"))
            if _may_clean_up(error, posted):
                self._quietly(media.delete_video_from_r2, result["asset"])
            else:
                self.stdout.write("     the site may still have saved it: check the lesson before retrying")
            return
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        minutes = result["duration_seconds"] // 60
        took = int(time.monotonic() - started)
        self.stdout.write(self.style.SUCCESS(
            f"     on the site: {minutes} min, {result['segment_count']} segments"
            f"{' (replaced the old video)' if answer.get('replaced') else ''} · {took} s"))

    # ------------------------------------------------------------------ documents

    def _documents(self, source, work):
        if self.options["only"]:
            return  # --only names lessons; files are uploaded in a run without it
        by_name = {p.name.lower(): p for p in source.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"}
        known = set()
        for document in self.documents:
            name = (document.get("source_name") or "").lower()
            known.add(name)
            path = by_name.get(name)
            if path is None:
                self.stdout.write(self.style.WARNING(f"  {document['title']}: {document.get('source_name')} not in the folder"))
                continue
            if document.get("ready") and not self.options["force"]:
                where = "in R2" if document.get("storage") == "r2" else "on the server"
                self.stdout.write(f"  {document['title']}: already on the site ({where})")
                continue
            if self.options["dry_run"]:
                self.stdout.write(f"  {document['title']}: would upload {path.name}")
                continue
            self._upload_document(document, path, work)
        for name, path in sorted(by_name.items()):
            if name not in known:
                self.stdout.write(self.style.WARNING(
                    f"  {path.name}: not in the course file list (apps/sat/admissions_course.py), skipped"))

    def _upload_document(self, document, path, work):
        self.stdout.write(f"  {document['title']}: rendering {path.name} ...")
        try:
            asset, pages = media.render_pdf_pages(path, root=work)
        except Exception as error:  # noqa: BLE001
            self.failures += 1
            self.stdout.write(self.style.ERROR(f"     rendering failed: {str(error)[:300]}"))
            return
        folder = media.local_asset_dir(work, media.DOC_DIR, asset)
        posted = False
        try:
            media.upload_doc_to_r2(asset, folder=folder)
            posted = True
            answer = self.transport("POST", "document/", {
                "slug": document["slug"], "asset": asset, "page_count": pages, "source_name": path.name,
            })
        except Exception as error:  # noqa: BLE001
            self.failures += 1
            self.stdout.write(self.style.ERROR(f"     failed: {str(error)[:300]}"))
            if _may_clean_up(error, posted):
                self._quietly(media.delete_doc_from_r2, asset)
            else:
                self.stdout.write("     the site may still have saved it: check the file before retrying")
            return
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        self.stdout.write(self.style.SUCCESS(
            f"     on the site: {pages} pages{' (replaced the old file)' if answer.get('replaced') else ''}"))

    @staticmethod
    def _quietly(function, *args):
        try:
            function(*args)
        except Exception:  # noqa: BLE001 - cleanup of an unregistered upload is best effort
            pass

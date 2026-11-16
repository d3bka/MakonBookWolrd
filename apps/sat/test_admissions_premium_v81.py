"""V81: SATMakon premium Admissions videos and PDFs must not leak.

Covers: login + access per lesson, signed tokens bound to user/object/session, encrypted
HLS rewriting, same-origin and rate limits, private no-store headers, X-Accel delivery,
watermarked PDF pages (the PDF itself is never served) and the import pipeline guards.
"""
import io
import shutil
import tempfile
from pathlib import Path
from unittest import mock, skipUnless

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.sat import admissions_media as media
from apps.sat.models import AdmissionsDocument, AdmissionsLesson, AdmissionsVideo

KEY = bytes(range(16))
PLAYLIST = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:6
#EXT-X-PLAYLIST-TYPE:VOD
#EXT-X-KEY:METHOD=AES-128,URI="key",IV=0x00000000000000000000000000000001
#EXTINF:6.0,
s0000.ts
#EXTINF:6.0,
s0001.ts
#EXTINF:6.0,
../../../etc/passwd
#EXT-X-ENDLIST
"""


class PremiumBase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.mkdtemp(prefix="premium-test-")
        cls._override = override_settings(MAKONBOOK_PREMIUM_ROOT=cls._tmp, MAKONBOOK_PREMIUM_ACCEL_PREFIX="")
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls._tmp, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.lessons = list(AdmissionsLesson.objects.order_by("order", "id"))
        self.free, self.locked = self.lessons[0], self.lessons[5]
        self.free_video = self.make_video(self.free)
        self.locked_video = self.make_video(self.locked)
        self.kid = User.objects.create_user("v81_kid", password="x")
        self.client.force_login(self.kid)

    def make_video(self, lesson):
        asset = media.new_asset_id()
        folder = media.video_dir(asset)
        folder.mkdir(parents=True)
        (folder / "index.m3u8").write_text(PLAYLIST, encoding="utf-8")
        (folder / "s0000.ts").write_bytes(b"ENCRYPTED-0" * 10)
        (folder / "s0001.ts").write_bytes(b"ENCRYPTED-1" * 10)
        return AdmissionsVideo.objects.create(lesson=lesson, asset=asset, key_hex=KEY.hex(), segment_count=2)

    def make_current_student(self, user=None):
        user = user or self.kid
        user.profile.hollihop_client_id = 990001 + user.pk
        user.profile.hollihop_status = "Занимается"
        user.profile.save()

    def playlist(self, lesson, client=None):
        return (client or self.client).get(reverse("admissions_video_playlist_root", args=[lesson.slug]))

    @staticmethod
    def urls_in(playlist_text):
        key = playlist_text.split('URI="', 1)[1].split('"', 1)[0]
        segments = [line for line in playlist_text.splitlines() if line and not line.startswith("#")]
        return key, segments


class VideoProtectionTests(PremiumBase):
    def test_playlist_points_only_at_checked_endpoints(self):
        response = self.playlist(self.free)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.apple.mpegurl")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")
        text = response.content.decode()
        key, segments = self.urls_in(text)
        self.assertTrue(key.startswith(reverse("admissions_video_key_root", args=[self.free.slug]) + "?t="))
        self.assertEqual(len(segments), 2)  # the "../../../etc/passwd" line is dropped
        self.assertNotIn("passwd", text)
        self.assertNotIn(self.free_video.asset, text)  # the storage folder name never leaves the server

    def test_key_and_segments_work_with_the_token(self):
        key, segments = self.urls_in(self.playlist(self.free).content.decode())
        key_response = self.client.get(key)
        self.assertEqual((key_response.status_code, key_response.content), (200, KEY))
        self.assertIn("no-store", key_response["Cache-Control"])
        segment = self.client.get(segments[0])
        self.assertEqual(segment.status_code, 200)
        self.assertEqual(b"".join(segment.streaming_content), b"ENCRYPTED-0" * 10)
        self.assertEqual(segment["Content-Disposition"], "inline")

    def test_links_are_useless_to_anyone_else(self):
        key, segments = self.urls_in(self.playlist(self.free).content.decode())
        anonymous = Client()
        self.assertEqual(anonymous.get(key).status_code, 302)          # login first
        self.assertEqual(anonymous.get(segments[0]).status_code, 302)
        other = Client()
        other.force_login(User.objects.create_user("v81_other", password="x"))
        self.assertEqual(other.get(key).status_code, 403)              # token belongs to someone else
        self.assertEqual(other.get(segments[0]).status_code, 403)
        same_user_new_session = Client()
        same_user_new_session.force_login(self.kid)
        self.assertEqual(same_user_new_session.get(key).status_code, 403)  # bound to the login session

    def test_tampered_or_missing_tokens_and_bad_names(self):
        key, segments = self.urls_in(self.playlist(self.free).content.decode())
        self.assertEqual(self.client.get(key.split("?")[0]).status_code, 403)
        self.assertEqual(self.client.get(key + "x").status_code, 403)
        token = key.split("?t=")[1]
        other_lesson_key = reverse("admissions_video_key_root", args=[self.lessons[1].slug]) + f"?t={token}"
        self.assertEqual(self.client.get(other_lesson_key).status_code, 403)
        bad = reverse("admissions_video_segment_root", args=[self.free.slug, "index.m3u8"]) + f"?t={token}"
        self.assertEqual(self.client.get(bad).status_code, 404)

    def test_locked_lessons_give_nothing_to_non_satmakon_students(self):
        self.assertEqual(self.playlist(self.locked).status_code, 404)
        url = reverse("admissions_video_key_root", args=[self.locked.slug]) + "?t=forged"
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_current_satmakon_students_watch_everything(self):
        self.make_current_student()
        response = self.playlist(self.locked)
        self.assertEqual(response.status_code, 200)
        key, _ = self.urls_in(response.content.decode())
        self.assertEqual(self.client.get(key).content, KEY)

    def test_a_student_who_left_loses_the_key_and_the_segments(self):
        from django.core.cache import cache

        self.make_current_student()
        key, segments = self.urls_in(self.playlist(self.locked).content.decode())
        self.assertEqual(self.client.get(segments[0]).status_code, 200)
        self.kid.profile.hollihop_status = "Закончил обучение"
        self.kid.profile.save()
        self.assertEqual(self.client.get(key).status_code, 403)       # at once
        cache.delete(f"adm-access:video:{self.locked_video.pk}:{self.kid.pk}")  # = two minutes later
        self.assertEqual(self.client.get(segments[0]).status_code, 403)

    def test_daily_cap(self):
        key, segments = self.urls_in(self.playlist(self.free).content.decode())
        with mock.patch.dict(media.DAILY_LIMITS, {"segment": 2}):
            codes = [self.client.get(segments[0]).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])

    def test_other_sites_cannot_pull_the_files(self):
        key, segments = self.urls_in(self.playlist(self.free).content.decode())
        self.assertEqual(self.client.get(key, HTTP_SEC_FETCH_SITE="cross-site").status_code, 403)
        self.assertEqual(self.client.get(segments[0], HTTP_SEC_FETCH_SITE="cross-site").status_code, 403)
        self.assertEqual(self.client.get(segments[0], HTTP_SEC_FETCH_SITE="same-origin").status_code, 200)

    def test_bulk_downloading_is_stopped(self):
        key, segments = self.urls_in(self.playlist(self.free).content.decode())
        with mock.patch.dict(media.RATE_LIMITS, {"segment": 3}):
            codes = [self.client.get(segments[0]).status_code for _ in range(5)]
        self.assertEqual(codes, [200, 200, 200, 429, 429])

    def test_staff_get_nothing(self):
        teacher = User.objects.create_user("v81_teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        client = Client()
        client.force_login(teacher)
        self.assertEqual(self.playlist(self.free, client).status_code, 404)

    @override_settings(MAKONBOOK_PREMIUM_ACCEL_PREFIX="/_premium/")
    def test_production_hands_the_file_to_nginx_internal_location(self):
        key, segments = self.urls_in(self.playlist(self.free).content.decode())
        response = self.client.get(segments[1])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Accel-Redirect"], f"/_premium/admissions/videos/{self.free_video.asset}/s0001.ts")
        self.assertEqual(response.content, b"")
        self.assertIn("no-store", response["Cache-Control"])

    def test_lesson_page_shows_the_player_not_a_file_link(self):
        page = self.client.get(reverse("admissions_section_root", args=[self.free.slug]))
        self.assertContains(page, "data-adm-player")
        self.assertContains(page, reverse("admissions_video_playlist_root", args=[self.free.slug]))
        self.assertContains(page, 'controlslist="nodownload')
        self.assertNotContains(page, ".mp4")
        self.assertNotContains(page, self.free_video.asset)
        self.assertContains(page, f"ID {self.kid.pk}")  # watermark
        locked = self.client.get(reverse("admissions_section_root", args=[self.locked.slug]))
        self.assertNotContains(locked, "data-adm-player")


class DocumentProtectionTests(PremiumBase):
    def setUp(self):
        super().setUp()
        self.open_doc = self.make_document("v81-open", self.lessons[2])      # lesson 3: free
        self.locked_doc = self.make_document("v81-locked", self.lessons[15])  # lesson 16: SATMakon only

    def make_document(self, slug, lesson):
        from PIL import Image

        asset = media.new_asset_id()
        folder = media.doc_dir(asset)
        folder.mkdir(parents=True)
        for number in (1, 2):
            Image.new("RGB", (700, 900), (255, 255, 255)).save(folder / f"p{number:03d}.jpg", "JPEG")
        document = AdmissionsDocument.objects.create(slug=slug, title=slug, asset=asset, page_count=2)
        document.lessons.add(lesson)
        return document

    def page_urls(self, document):
        response = self.client.get(reverse("admissions_document_root", args=[document.slug]))
        return response, response.context.get("document_pages") or []

    def test_open_file_shows_watermarked_pages_never_the_pdf(self):
        response, pages = self.page_urls(self.open_doc)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(len(pages), 2)
        self.assertNotContains(response, ".pdf")
        image = self.client.get(pages[0])
        self.assertEqual((image.status_code, image["Content-Type"]), (200, "image/jpeg"))
        original = (media.doc_dir(self.open_doc.asset) / "p001.jpg").read_bytes()
        self.assertNotEqual(image.content, original)  # stamped with the viewer's watermark
        from PIL import Image
        stamped = Image.open(io.BytesIO(image.content)).convert("L")
        self.assertLess(min(stamped.getdata()), 250)  # a blank white page now has visible marks

    def test_locked_file_has_no_pages_for_non_satmakon_students(self):
        response, pages = self.page_urls(self.locked_doc)
        self.assertEqual(pages, [])
        self.assertContains(response, "Available only to current SATMakon students")
        forged = reverse("admissions_document_page_root", args=[self.locked_doc.slug, 1]) + "?t=forged"
        self.assertEqual(self.client.get(forged).status_code, 403)

    def test_page_links_need_this_user_and_a_valid_page(self):
        _, pages = self.page_urls(self.open_doc)
        other = Client()
        other.force_login(User.objects.create_user("v81_doc_other", password="x"))
        self.assertEqual(other.get(pages[0]).status_code, 403)
        self.assertEqual(Client().get(pages[0]).status_code, 302)
        out_of_range = pages[0].replace("/page/1/", "/page/9/")
        self.assertEqual(self.client.get(out_of_range).status_code, 404)

    def test_current_students_read_every_file_and_home_lists_them(self):
        self.make_current_student()
        _, pages = self.page_urls(self.locked_doc)
        self.assertEqual(len(pages), 2)
        home = self.client.get(reverse("admissions_root"))
        self.assertContains(home, reverse("admissions_document_root", args=[self.locked_doc.slug]))

    def test_a_file_shared_with_a_paid_lesson_stays_paid(self):
        self.open_doc.lessons.add(self.lessons[10])
        response, pages = self.page_urls(self.open_doc)
        self.assertEqual(pages, [])
        self.make_current_student()
        self.assertEqual(len(self.page_urls(self.open_doc)[1]), 2)

    def test_pages_stop_when_access_ends(self):
        from django.core.cache import cache

        _, pages = self.page_urls(self.open_doc)
        self.assertEqual(self.client.get(pages[0]).status_code, 200)
        self.open_doc.lessons.add(self.lessons[10])  # the file becomes paid
        cache.delete(f"adm-access:doc:{self.open_doc.pk}:{self.kid.pk}")
        self.assertEqual(self.client.get(pages[0]).status_code, 403)

    def test_watermark_names_the_viewer(self):
        self.kid.first_name, self.kid.last_name = "Азиз", "Каримов"
        self.kid.save()
        text = media.watermark_text(self.kid)
        self.assertIn("v81_kid", text)
        self.assertIn(f"ID {self.kid.pk}", text)


class ImportPipelineTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="premium-import-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_pdf_pages_are_rendered_into_the_private_folder(self):
        import fitz

        source = self.tmp / "src"
        source.mkdir()
        pdf = fitz.open()
        for _ in range(3):
            pdf.new_page().insert_text((72, 72), "SATMakon test page")
        pdf.save(str(source / "Merit scholarships.pdf"))
        pdf.close()
        with override_settings(MAKONBOOK_PREMIUM_ROOT=str(self.tmp / "premium")):
            call_command("import_admissions_media", str(source), "--docs-only", stdout=io.StringIO())
            document = AdmissionsDocument.objects.get(slug="merit-scholarships")
            self.assertEqual(document.page_count, 3)
            pages = sorted(p.name for p in media.doc_dir(document.asset).iterdir())
        self.assertEqual(pages, ["p001.jpg", "p002.jpg", "p003.jpg"])
        self.assertFalse(list((self.tmp / "premium").rglob("*.pdf")))  # the PDF is not copied

    def test_refuses_a_public_folder(self):
        with override_settings(MAKONBOOK_PREMIUM_ROOT=str(Path(settings.MEDIA_ROOT) / "premium")):
            with self.assertRaises(CommandError):
                call_command("import_admissions_media", str(self.tmp), stdout=io.StringIO())

    @skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed")
    def test_videos_become_encrypted_hls_without_a_key_file(self):
        import subprocess

        source = self.tmp / "src"
        source.mkdir()
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25",
                        "-f", "lavfi", "-i", "sine", "-t", "8", "-c:v", "libx264", "-c:a", "aac", "-shortest",
                        str(source / "Lesson 1 - Introduction.mp4")], check=True)
        with override_settings(MAKONBOOK_PREMIUM_ROOT=str(self.tmp / "premium")):
            call_command("import_admissions_media", str(source), "--videos-only", stdout=io.StringIO())
            video = AdmissionsVideo.objects.get(lesson__order=1)
            folder = media.video_dir(video.asset)
            self.assertIn("METHOD=AES-128", (folder / "index.m3u8").read_text())
        self.assertEqual(len(bytes.fromhex(video.key_hex)), 16)
        names = {p.suffix for p in (self.tmp / "premium").rglob("*") if p.is_file()}
        self.assertEqual(names, {".m3u8", ".ts"})  # no key file is left on disk


class ProtectionConfigTests(TestCase):
    def test_premium_content_never_reaches_git_or_the_image(self):
        base = Path(settings.BASE_DIR)
        for name in (".gitignore", ".dockerignore"):
            text = (base / name).read_text(encoding="utf-8")
            self.assertIn("private_content/", text, name)
            self.assertIn("Lessons/", text, name)
            self.assertIn("*.mp4", text, name)

    def test_player_uses_the_self_hosted_hls_library(self):
        base = Path(settings.BASE_DIR)
        template = (base / "templates" / "sat" / "admissions_lesson.html").read_text(encoding="utf-8")
        self.assertIn("assets/vendor/hls.js/hls.min.js", template)
        self.assertNotIn("cdn.jsdelivr.net/npm/hls.js", template)
        self.assertTrue((base / "static" / "assets" / "vendor" / "hls.js" / "hls.min.js").is_file())

    def test_nginx_serves_premium_files_only_internally(self):
        conf = (Path(settings.BASE_DIR) / "nginx" / "default.conf").read_text(encoding="utf-8")
        block = conf.split("location /_premium/", 1)[1].split("}", 1)[0]
        self.assertIn("internal;", block)
        self.assertIn("no-store", block)

    def test_premium_root_is_not_public(self):
        root = Path(settings.MAKONBOOK_PREMIUM_ROOT).resolve()
        media_root = Path(settings.MEDIA_ROOT).resolve()
        self.assertNotEqual(root, media_root)
        self.assertNotIn(media_root, root.parents)

"""V86: upload Admissions videos and PDFs from a PC straight to the private R2 bucket.

The site never receives video or PDF bytes: only the lesson record (asset id, AES key,
playlist) through a token-protected HTTPS API. PDF pages are read back from R2 and stamped
with the viewer's watermark before they leave the server.
"""
import io
import json
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.sat import admissions_media as media
from apps.sat.management.commands import upload_admissions_media as upload_cmd
from apps.sat.models import AdmissionsDocument, AdmissionsLesson, AdmissionsVideo
from apps.sat.test_admissions_premium_v81 import PremiumBase

TOKEN = "t0ken-" + "x" * 40
BUCKET = "makon-premium-v86-test"
R2 = dict(
    MAKONBOOK_PREMIUM_R2_BUCKET=BUCKET,
    MAKONBOOK_PREMIUM_R2_ENDPOINT_URL="https://acc.r2.example",
    MAKONBOOK_PREMIUM_R2_ACCESS_KEY_ID="id",
    MAKONBOOK_PREMIUM_R2_SECRET_ACCESS_KEY="secret",
    MAKONBOOK_MEDIA_UPLOAD_TOKEN=TOKEN,
    MAKONBOOK_MEDIA_UPLOAD_SITE="https://makonbook.example",
)


def playlist(count, extra=""):
    lines = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-TARGETDURATION:6", "#EXT-X-PLAYLIST-TYPE:VOD",
             '#EXT-X-KEY:METHOD=AES-128,URI="key",IV=0x00000000000000000000000000000001']
    for number in range(count):
        lines += ["#EXTINF:6.0,", f"s{number:04d}.ts"]
    return "\n".join(lines) + extra + "\n#EXT-X-ENDLIST\n"


class _Body(io.BytesIO):
    pass


class FakeR2:
    """Just enough of the S3 client for the upload and delivery code."""

    def __init__(self):
        self.objects = {}

    def upload_file(self, filename, bucket, key, ExtraArgs=None):
        assert bucket == BUCKET
        self.objects[key] = Path(filename).read_bytes()

    def put(self, key, data=b"x"):
        self.objects[key] = data

    def get_paginator(self, _name):
        fake = self

        class Paginator:
            def paginate(self, Bucket, Prefix):
                return [{"Contents": [{"Key": key} for key in sorted(fake.objects) if key.startswith(Prefix)]}]

        return Paginator()

    def delete_objects(self, Bucket, Delete):
        for item in Delete["Objects"]:
            self.objects.pop(item["Key"], None)

    def get_object(self, Bucket, Key):
        return {"Body": _Body(self.objects[Key])}

    def prefix(self, prefix):
        return [key for key in self.objects if key.startswith(prefix)]


@override_settings(**R2)
class MediaApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.r2 = FakeR2()
        patcher = mock.patch.object(media, "r2_client", return_value=self.r2)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.lesson = AdmissionsLesson.objects.order_by("order", "id").first()
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}

    def post(self, name, payload, **extra):
        headers = {**self.auth, **extra}
        return self.client.post(reverse(name), data=json.dumps(payload), content_type="application/json",
                                secure=True, **headers)

    def video_payload(self, asset=None, count=3, **changes):
        asset = asset or media.new_asset_id()
        data = {"lesson_order": self.lesson.order, "asset": asset, "key_hex": "ab" * 16,
                "playlist_text": playlist(count), "duration_seconds": 900, "segment_count": count,
                "source_name": "Lesson 1 - Intro.mp4"}
        data.update(changes)
        return data

    def put_segments(self, asset, count=3):
        for number in range(count):
            self.r2.put(f"{media.VIDEO_DIR}/{asset}/s{number:04d}.ts")

    # -------------------------------------------------------------- access

    @override_settings(MAKONBOOK_MEDIA_UPLOAD_TOKEN="")
    def test_api_is_off_without_a_token(self):
        response = self.client.get(reverse("admissions_media_api_status"), secure=True, **self.auth)
        self.assertEqual(response.status_code, 404)

    @override_settings(MAKONBOOK_MEDIA_UPLOAD_TOKEN="short")
    def test_a_short_token_does_not_switch_it_on(self):
        response = self.client.get(reverse("admissions_media_api_status"), secure=True,
                                   HTTP_AUTHORIZATION="Bearer short")
        self.assertEqual(response.status_code, 404)

    def test_wrong_tokens_are_refused_then_the_ip_is_blocked(self):
        url = reverse("admissions_media_api_status")
        for _ in range(10):
            self.assertEqual(self.client.get(url, secure=True, HTTP_AUTHORIZATION="Bearer nope").status_code, 403)
        self.assertEqual(self.client.get(url, secure=True).status_code, 429)
        self.assertEqual(self.client.get(url, secure=True, **self.auth).status_code, 429)

    @override_settings(DEBUG=False)
    def test_https_only(self):
        response = self.client.get(reverse("admissions_media_api_status"), **self.auth)
        self.assertEqual(response.status_code, 403)

    def test_a_logged_in_admin_without_the_token_gets_nothing(self):
        from django.contrib.auth.models import User

        self.client.force_login(User.objects.create_superuser("v86boss", password="x"))
        response = self.client.get(reverse("admissions_media_api_status"), secure=True)
        self.assertEqual(response.status_code, 403)

    def test_status_lists_lessons_files_and_the_bucket(self):
        response = self.client.get(reverse("admissions_media_api_status"), secure=True, **self.auth)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["bucket"], BUCKET)
        self.assertEqual(data["lessons"][0]["order"], self.lesson.order)
        self.assertIsNone(data["lessons"][0]["video"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn("key_hex", response.content.decode())

    # -------------------------------------------------------------- videos

    def test_registers_a_video_whose_segments_are_in_r2(self):
        payload = self.video_payload()
        self.put_segments(payload["asset"])
        response = self.post("admissions_media_api_video", payload)
        self.assertEqual(response.status_code, 200, response.content)
        video = AdmissionsVideo.objects.get(lesson=self.lesson)
        self.assertEqual((video.asset, video.key_hex, video.storage, video.segment_count),
                         (payload["asset"], "ab" * 16, AdmissionsVideo.STORAGE_R2, 3))
        self.assertEqual(video.playlist_text, payload["playlist_text"])
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.minutes, 15)
        self.assertNotIn("ab" * 16, response.content.decode())

    def test_replacing_a_video_deletes_the_old_segments(self):
        first = self.video_payload()
        self.put_segments(first["asset"])
        self.post("admissions_media_api_video", first)
        second = self.video_payload()
        self.put_segments(second["asset"])
        response = self.post("admissions_media_api_video", second)
        self.assertTrue(response.json()["replaced"])
        self.assertEqual(self.r2.prefix(f"{media.VIDEO_DIR}/{first['asset']}/"), [])
        self.assertEqual(len(self.r2.prefix(f"{media.VIDEO_DIR}/{second['asset']}/")), 3)
        self.assertEqual(AdmissionsVideo.objects.get(lesson=self.lesson).asset, second["asset"])

    def test_refuses_records_without_the_segments_in_r2(self):
        payload = self.video_payload()
        self.put_segments(payload["asset"], count=2)
        response = self.post("admissions_media_api_video", payload)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(AdmissionsVideo.objects.exists())

    def test_refuses_bad_records(self):
        cases = [
            (self.video_payload(key_hex="zz" * 16), 400),
            (self.video_payload(asset="../../etc"), 400),
            (self.video_payload(playlist_text=playlist(3, "\n#EXTINF:6.0,\nhttps://evil.example/x.ts")), 400),
            (self.video_payload(playlist_text=playlist(3).replace("METHOD=AES-128", "METHOD=NONE")), 400),
            (self.video_payload(playlist_text=playlist(2)), 400),
            (self.video_payload(lesson_order=999), 404),
            (self.video_payload(duration_seconds=-5), 400),
        ]
        for payload, status in cases:
            with self.subTest(payload={k: v for k, v in payload.items() if k != "playlist_text"}):
                self.put_segments(payload["asset"]) if media.ASSET_NAME.match(payload["asset"]) else None
                self.assertEqual(self.post("admissions_media_api_video", payload).status_code, status)
        bad_json = self.client.post(reverse("admissions_media_api_video"), data="[1]",
                                    content_type="application/json", secure=True, **self.auth)
        self.assertEqual(bad_json.status_code, 400)
        self.assertFalse(AdmissionsVideo.objects.exists())

    def test_get_is_not_allowed_on_writes(self):
        response = self.client.get(reverse("admissions_media_api_video"), secure=True, **self.auth)
        self.assertEqual(response.status_code, 405)

    # -------------------------------------------------------------- documents

    def test_registers_a_document_and_replaces_the_old_pages(self):
        document = AdmissionsDocument.objects.create(slug="v86-guide", title="Guide", source_name="Guide.pdf")
        asset = media.new_asset_id()
        for number in (1, 2):
            self.r2.put(media.r2_page_key(asset, number))
        response = self.post("admissions_media_api_document", {"slug": "v86-guide", "asset": asset, "page_count": 2})
        self.assertEqual(response.status_code, 200, response.content)
        document.refresh_from_db()
        self.assertEqual((document.asset, document.page_count, document.storage), (asset, 2, "r2"))
        newer = media.new_asset_id()
        self.r2.put(media.r2_page_key(newer, 1))
        self.post("admissions_media_api_document", {"slug": "v86-guide", "asset": newer, "page_count": 1})
        self.assertEqual(self.r2.prefix(f"{media.DOC_DIR}/{asset}/"), [])

    def test_document_pages_must_be_in_r2(self):
        AdmissionsDocument.objects.create(slug="v86-guide", title="Guide")
        response = self.post("admissions_media_api_document",
                             {"slug": "v86-guide", "asset": media.new_asset_id(), "page_count": 4})
        self.assertEqual(response.status_code, 409)
        response = self.post("admissions_media_api_document", {"slug": "missing", "asset": media.new_asset_id(),
                                                                "page_count": 1})
        self.assertEqual(response.status_code, 404)


@override_settings(**R2)
class R2PagesAreStampedTests(PremiumBase):
    def test_pages_from_r2_get_the_viewer_watermark(self):
        from PIL import Image

        r2 = FakeR2()
        asset = media.new_asset_id()
        buffer = io.BytesIO()
        Image.new("RGB", (700, 900), (255, 255, 255)).save(buffer, "JPEG")
        r2.put(media.r2_page_key(asset, 1), buffer.getvalue())
        document = AdmissionsDocument.objects.create(slug="v86-r2", title="R2 file", asset=asset, page_count=1,
                                                     storage=AdmissionsVideo.STORAGE_R2)
        document.lessons.add(self.lessons[2])
        with mock.patch.object(media, "r2_client", return_value=r2):
            response = self.client.get(reverse("admissions_document_root", args=[document.slug]))
            page = self.client.get(response.context["document_pages"][0])
        self.assertEqual((page.status_code, page["Content-Type"]), (200, "image/jpeg"))
        self.assertNotEqual(page.content, buffer.getvalue())
        self.assertIn("no-store", page["Cache-Control"])
        stamped = Image.open(io.BytesIO(page.content)).convert("L")
        self.assertLess(min(stamped.getdata()), 250)

    def test_a_missing_r2_page_is_not_a_crash(self):
        document = AdmissionsDocument.objects.create(slug="v86-gone", title="Gone", asset=media.new_asset_id(),
                                                     page_count=1, storage=AdmissionsVideo.STORAGE_R2)
        document.lessons.add(self.lessons[2])
        with mock.patch.object(media, "r2_client", return_value=FakeR2()):
            response = self.client.get(reverse("admissions_document_root", args=[document.slug]))
            page = self.client.get(response.context["document_pages"][0])
        self.assertEqual(page.status_code, 503)


def fake_encrypt(source, *, reencode=False, segment_seconds=6, root=None):
    asset = media.new_asset_id()
    folder = media.local_asset_dir(root, media.VIDEO_DIR, asset)
    folder.mkdir(parents=True)
    (folder / "index.m3u8").write_text(playlist(2), encoding="utf-8")
    (folder / "s0000.ts").write_bytes(b"ENC0")
    (folder / "s0001.ts").write_bytes(b"ENC1")
    return {"asset": asset, "key_hex": "cd" * 16, "duration_seconds": 125, "segment_count": 2}


@override_settings(**R2)
class UploadFromPcCommandTests(TestCase):
    def setUp(self):
        cache.clear()
        self.r2 = FakeR2()
        self.source = Path(tempfile.mkdtemp(prefix="lessons-"))
        self.addCleanup(shutil.rmtree, self.source, True)
        self.premium = tempfile.mkdtemp(prefix="premium-")
        self.addCleanup(shutil.rmtree, self.premium, True)
        self.lesson = AdmissionsLesson.objects.order_by("order", "id").first()
        (self.source / f"Lesson {self.lesson.order} - Intro.mp4").write_bytes(b"MP4" * 100)
        self.document = AdmissionsDocument.objects.create(slug="v86-pdf", title="PDF guide", source_name="Guide.pdf")
        import fitz

        with fitz.open() as pdf:
            for _ in range(2):
                pdf.new_page(width=300, height=400).insert_text((40, 60), "SATMakon")
            pdf.save(str(self.source / "Guide.pdf"))
        self.work_dirs = []
        client = self.client

        def transport(command, method, path, payload=None):
            url = "/api/admissions-media/" + path
            if method == "GET":
                response = client.get(url, secure=True, HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
            else:
                response = client.post(url, data=json.dumps(payload), content_type="application/json",
                                       secure=True, HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
            if response.status_code >= 400:
                raise upload_cmd.ApiError(f"HTTP {response.status_code} {response.json().get('error', '')}")
            return response.json()

        real_tempdir = tempfile.TemporaryDirectory

        def tracking_tempdir(*args, **kwargs):
            folder = real_tempdir(*args, **kwargs)
            self.work_dirs.append(folder.name)
            return folder

        for patcher in (
            mock.patch.object(media, "r2_client", return_value=self.r2),
            mock.patch.object(upload_cmd.Command, "transport", autospec=True, side_effect=transport),
            mock.patch.object(upload_cmd.Command, "_check_ffmpeg", autospec=True),
            mock.patch.object(media, "encrypt_video_to_hls", side_effect=fake_encrypt),
            mock.patch.object(upload_cmd.tempfile, "TemporaryDirectory", side_effect=tracking_tempdir),
            override_settings(MAKONBOOK_PREMIUM_ROOT=self.premium),
        ):
            patcher.start() if hasattr(patcher, "start") else patcher.enable()
            self.addCleanup(patcher.stop if hasattr(patcher, "stop") else patcher.disable)

    def run_command(self, *args):
        out = io.StringIO()
        call_command("upload_admissions_media", str(self.source), *args, stdout=out)
        return out.getvalue()

    def test_uploads_videos_and_pages_to_r2_and_registers_them(self):
        output = self.run_command()
        video = AdmissionsVideo.objects.get(lesson=self.lesson)
        self.assertEqual((video.storage, video.key_hex, video.segment_count), ("r2", "cd" * 16, 2))
        self.assertEqual(sorted(self.r2.prefix(f"{media.VIDEO_DIR}/{video.asset}/")),
                         [f"{media.VIDEO_DIR}/{video.asset}/s0000.ts", f"{media.VIDEO_DIR}/{video.asset}/s0001.ts"])
        self.document.refresh_from_db()
        self.assertEqual((self.document.storage, self.document.page_count), ("r2", 2))
        self.assertEqual(len(self.r2.prefix(f"{media.DOC_DIR}/{self.document.asset}/")), 2)
        # Neither the key nor the playlist nor the mp4/PDF went to R2 or to the server folder.
        self.assertFalse(any(key.endswith((".m3u8", ".mp4", ".pdf", ".bin")) for key in self.r2.objects))
        self.assertEqual(list(Path(self.premium).rglob("*")), [])
        self.assertTrue(self.work_dirs and not any(Path(d).exists() for d in self.work_dirs))
        self.assertNotIn("cd" * 16, output)
        self.assertIn("Done.", output)
        self.assertTrue((self.source / f"Lesson {self.lesson.order} - Intro.mp4").exists())

    def test_second_run_skips_what_the_site_has(self):
        self.run_command()
        objects = dict(self.r2.objects)
        output = self.run_command()
        self.assertIn("already on the site", output)
        self.assertEqual(self.r2.objects, objects)

    def test_force_replaces_one_lesson(self):
        self.run_command()
        old = AdmissionsVideo.objects.get(lesson=self.lesson).asset
        self.run_command("--force", "--only", str(self.lesson.order))
        new = AdmissionsVideo.objects.get(lesson=self.lesson).asset
        self.assertNotEqual(old, new)
        self.assertEqual(self.r2.prefix(f"{media.VIDEO_DIR}/{old}/"), [])

    def test_dry_run_uploads_nothing(self):
        output = self.run_command("--dry-run")
        self.assertIn("would upload", output)
        self.assertEqual(self.r2.objects, {})
        self.assertFalse(AdmissionsVideo.objects.exists())

    def test_a_refused_record_removes_its_upload(self):
        with mock.patch("apps.sat.views_admissions_upload._check_playlist", return_value="nope"):
            with self.assertRaises(CommandError):
                self.run_command("--videos-only")
        self.assertEqual(self.r2.objects, {})

    def test_a_lost_answer_keeps_the_upload(self):
        def lost(command, method, path, payload=None):
            if method == "GET":
                return {"bucket": BUCKET, "lessons": [{"order": self.lesson.order, "slug": "x", "title": "T", "video": None}],
                        "documents": []}
            raise upload_cmd.ApiError("cannot reach", answered=False)

        with mock.patch.object(upload_cmd.Command, "transport", new=lost):
            with self.assertRaises(CommandError):
                self.run_command("--videos-only")
        self.assertEqual(len(self.r2.objects), 2)

    def test_refuses_a_different_bucket_plain_http_and_missing_token(self):
        def other_bucket(command, method, path, payload=None):
            return {"bucket": "another-private-bucket", "lessons": [], "documents": []}

        with mock.patch.object(upload_cmd.Command, "transport", new=other_bucket):
            with self.assertRaisesMessage(CommandError, "bucket"):
                self.run_command()
        self.assertEqual(self.r2.objects, {})
        with self.assertRaisesMessage(CommandError, "https"):
            self.run_command("--site", "http://makonbook.example")
        with override_settings(MAKONBOOK_MEDIA_UPLOAD_TOKEN=""):
            with self.assertRaisesMessage(CommandError, "MAKONBOOK_MEDIA_UPLOAD_TOKEN"):
                self.run_command()


@override_settings(**R2)
class PushCommandMovesFilesTests(PremiumBase):
    def test_push_moves_local_pages_to_r2(self):
        from PIL import Image

        asset = media.new_asset_id()
        folder = media.doc_dir(asset)
        folder.mkdir(parents=True)
        Image.new("RGB", (50, 50), (255, 255, 255)).save(folder / "p001.jpg", "JPEG")
        document = AdmissionsDocument.objects.create(slug="v86-push", title="Push", asset=asset, page_count=1)
        r2 = FakeR2()
        r2.head_bucket = lambda Bucket: {}
        with mock.patch.object(media, "r2_client", return_value=r2), \
                mock.patch.object(media, "upload_video_to_r2", return_value=2):
            call_command("push_admissions_media_to_r2", stdout=io.StringIO())
        document.refresh_from_db()
        self.assertEqual(document.storage, "r2")
        self.assertEqual(len(r2.prefix(f"{media.DOC_DIR}/{asset}/")), 1)
        self.assertFalse(folder.exists())

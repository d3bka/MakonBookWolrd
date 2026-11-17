"""V82: private R2 bucket for encrypted segments, device limit, key log and limits."""
import io
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, override_settings

from apps.sat import admissions_media as media
from apps.sat.models import AdmissionsKeyLog, AdmissionsMediaSession, AdmissionsVideo
from apps.sat.test_admissions_premium_v81 import KEY, PremiumBase

R2 = dict(MAKONBOOK_PREMIUM_R2_BUCKET="makon-premium-private", MAKONBOOK_PREMIUM_R2_ENDPOINT_URL="https://acc.r2.example",
          MAKONBOOK_PREMIUM_R2_ACCESS_KEY_ID="id", MAKONBOOK_PREMIUM_R2_SECRET_ACCESS_KEY="secret")


class R2DeliveryTests(PremiumBase):
    def test_r2_segments_are_short_lived_redirects_after_the_same_checks(self):
        AdmissionsVideo.objects.filter(pk=self.free_video.pk).update(storage=AdmissionsVideo.STORAGE_R2)
        key, segments = self.urls_in(self.playlist(self.free).content.decode())
        with mock.patch.object(media, "presigned_segment_url", return_value="https://acc.r2.example/x?X-Amz-Expires=60") as sign:
            response = self.client.get(segments[0])
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], "https://acc.r2.example/x?X-Amz-Expires=60")
            self.assertIn("no-store", response["Cache-Control"])
            sign.assert_called_once_with(self.free_video.asset, "s0000.ts")
            other = Client()
            other.force_login(User.objects.create_user("v82_other", password="x"))
            self.assertEqual(other.get(segments[0]).status_code, 403)  # no redirect for anyone else
            self.assertEqual(sign.call_count, 1)

    def test_playlist_comes_from_the_database(self):
        AdmissionsVideo.objects.filter(pk=self.free_video.pk).update(
            playlist_text='#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key"\ns0005.ts\n')
        _, segments = self.urls_in(self.playlist(self.free).content.decode())
        self.assertEqual(len(segments), 1)
        self.assertIn("/video/s0005.ts?t=", segments[0])

    @override_settings(**R2)
    def test_presigned_links_are_private_and_brief(self):
        client = mock.Mock()
        client.generate_presigned_url.return_value = "https://signed"
        with mock.patch.object(media, "r2_client", return_value=client), override_settings(MAKONBOOK_PREMIUM_R2_URL_TTL=60):
            self.assertEqual(media.presigned_segment_url("a" * 32, "s0001.ts"), "https://signed")
        args, kwargs = client.generate_presigned_url.call_args
        self.assertEqual(kwargs["ExpiresIn"], 60)
        self.assertEqual(kwargs["Params"]["Bucket"], "makon-premium-private")
        self.assertEqual(kwargs["Params"]["Key"], f"admissions/videos/{'a' * 32}/s0001.ts")
        self.assertIn("no-store", kwargs["Params"]["ResponseCacheControl"])
        with self.assertRaises(ValueError):
            media.r2_segment_key("a" * 32, "../index.m3u8")

    @override_settings(**dict(R2, MAKONBOOK_PREMIUM_R2_BUCKET="public-media", AWS_STORAGE_BUCKET_NAME="public-media"))
    def test_the_public_media_bucket_is_refused(self):
        with self.assertRaises(RuntimeError):
            media.assert_private_bucket()
        with self.assertRaises(CommandError):
            call_command("push_admissions_media_to_r2", "--check", stdout=io.StringIO())

    @override_settings(**R2)
    def test_upload_checks_every_segment_arrived(self):
        client = mock.Mock()
        client.get_paginator.return_value.paginate.return_value = [{"Contents": [{"Key": "a"}, {"Key": "b"}]}]
        with mock.patch.object(media, "r2_client", return_value=client):
            self.assertEqual(media.upload_video_to_r2(self.free_video.asset), 2)
            uploaded = sorted(call.args[2] for call in client.upload_file.call_args_list)
            self.assertEqual(uploaded, [f"admissions/videos/{self.free_video.asset}/s0000.ts",
                                        f"admissions/videos/{self.free_video.asset}/s0001.ts"])
            for call in client.upload_file.call_args_list:
                self.assertNotIn("index.m3u8", call.args[2])  # the playlist and key never go to R2
            client.get_paginator.return_value.paginate.return_value = [{"Contents": [{"Key": "a"}]}]
            with self.assertRaises(RuntimeError):
                media.upload_video_to_r2(self.free_video.asset)

    @override_settings(**R2)
    def test_push_command_moves_local_videos_and_deletes_server_copies(self):
        folder = media.video_dir(self.free_video.asset)
        with mock.patch.object(media, "r2_client") as client, \
                mock.patch.object(media, "upload_video_to_r2", return_value=2) as upload:
            client.return_value.head_bucket.return_value = {}
            call_command("push_admissions_media_to_r2", stdout=io.StringIO())
        self.assertEqual(upload.call_count, 2)
        self.free_video.refresh_from_db()
        self.assertEqual(self.free_video.storage, AdmissionsVideo.STORAGE_R2)
        self.assertIn("METHOD=AES-128", self.free_video.playlist_text)
        self.assertFalse(folder.exists())

    def test_push_command_needs_settings(self):
        with self.assertRaises(CommandError):
            call_command("push_admissions_media_to_r2", stdout=io.StringIO())


class DeviceAndKeyLogTests(PremiumBase):
    def device(self):
        client = Client()
        client.force_login(self.kid)
        return client

    def key_status(self, client, lesson):
        key, _ = self.urls_in(self.playlist(lesson, client).content.decode())
        return client, key

    @override_settings(MAKONBOOK_PREMIUM_MAX_DEVICES=2)
    def test_a_third_device_switches_off_the_oldest(self):
        from django.core.cache import cache

        a, key_a = self.key_status(self.device(), self.free)
        b, key_b = self.key_status(self.device(), self.free)
        self.assertEqual(a.get(key_a).status_code, 200)
        c, key_c = self.key_status(self.device(), self.free)
        cache.clear()  # = a minute later
        response = a.get(key_a)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response["X-Makon-Reason"], "device")
        self.assertEqual(b.get(key_b).status_code, 200)
        self.assertEqual(c.get(key_c).status_code, 200)
        self.assertEqual(AdmissionsMediaSession.objects.filter(user=self.kid, revoked_at__isnull=True).count(), 2)
        a, key_a = self.key_status(a, self.free)  # reopening the lesson takes the place back
        cache.clear()
        self.assertEqual(a.get(key_a).status_code, 200)
        self.assertEqual(b.get(key_b).status_code, 409)

    def test_every_key_is_logged_without_the_key(self):
        _, key = self.key_status(self.client, self.free)
        self.assertEqual(self.client.get(key, REMOTE_ADDR="10.1.2.3").content, KEY)
        row = AdmissionsKeyLog.objects.get(user=self.kid)
        self.assertEqual((row.video_id, row.ip, row.allowed), (self.free_video.pk, "10.1.2.3", True))
        self.assertNotIn(KEY.hex(), " ".join(str(v) for v in AdmissionsKeyLog.objects.values_list().first()))

    @override_settings(MAKONBOOK_PREMIUM_MAX_VIDEOS_PER_HOUR=1)
    def test_keys_for_too_many_different_videos_are_refused(self):
        self.make_current_student()
        _, first = self.key_status(self.client, self.free)
        _, second = self.key_status(self.client, self.locked)
        self.assertEqual(self.client.get(first).status_code, 200)
        self.assertEqual(self.client.get(first).status_code, 200)   # the same video again is fine
        self.assertEqual(self.client.get(second).status_code, 429)
        self.assertTrue(AdmissionsKeyLog.objects.filter(user=self.kid, allowed=False).exists())

    def test_client_ip_cannot_be_forged_by_the_student(self):
        from django.test import RequestFactory

        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="6.6.6.6", REMOTE_ADDR="10.0.0.5")
        self.assertEqual(media.client_ip(request), "10.0.0.5")
        request = RequestFactory().get("/", HTTP_X_REAL_IP="not-an-ip", REMOTE_ADDR="10.0.0.5")
        self.assertEqual(media.client_ip(request), "10.0.0.5")
        _, key = self.key_status(self.client, self.free)
        self.assertEqual(self.client.get(key, HTTP_X_FORWARDED_FOR="abc").status_code, 200)

    def test_short_phone_numbers_are_not_half_revealed(self):
        self.kid.profile.phone_number = "1234567"
        self.kid.profile.save()
        self.assertEqual(media.masked_phone(self.kid), "")

    @override_settings(MAKONBOOK_PREMIUM_R2_ALLOWED_ORIGINS=["*"], **R2)
    def test_cors_refuses_wildcards(self):
        with self.assertRaises(RuntimeError):
            media.apply_bucket_cors()

    def test_watermark_shows_a_masked_phone(self):
        self.kid.profile.phone_number = "+998 90 123 45 12"
        self.kid.profile.save()
        self.assertEqual(media.masked_phone(self.kid), "+99890•••••12")
        self.assertIn("+99890*****12", media.watermark_text(self.kid))
        page = self.client.get(f"/admissions/{self.free.slug}/")
        self.assertContains(page, "+99890•••••12")
        self.assertNotContains(page, "1234512")

"""V102: heartbeats, alerts when a part of MakonBook goes quiet, and the System health page."""
import os
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.base import system_health
from apps.base.models import SystemHeartbeat

BROKER_OK = {"configured": True, "ok": True, "queued": 0, "error": ""}
BROKER_DOWN = {"configured": True, "ok": False, "queued": None, "error": "ConnectionError"}


def heartbeat(component, minutes_ago, **extra):
    seen = None if minutes_ago is None else timezone.now() - timedelta(minutes=minutes_ago)
    row, _ = SystemHeartbeat.objects.update_or_create(component=component, defaults={"last_seen": seen, **extra})
    return row


@override_settings(
    CELERY_BROKER_URL="redis://127.0.0.1:6399/1",
    MONITORING_SITE_CHECK_URL="",
    MONITORING_TELEGRAM_CHAT_ID="",
    MONITORING_ALERT_EMAILS="ops@makonbook.example",
    HOLLIHOP_ENABLED=False,
)
class WatchTests(TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": ""})
        env.start()
        self.addCleanup(env.stop)
        broker = mock.patch.object(system_health, "check_broker", return_value=BROKER_OK)
        self.check_broker = broker.start()
        self.addCleanup(broker.stop)
        heartbeat("broker", 0)

    def watch(self):
        with mock.patch.object(system_health, "send_alert", return_value={"delivered": 1}) as send:
            sent = system_health.run_watch("web")
        return sent, send

    def test_celery_task_records_its_heartbeat(self):
        from apps.base.tasks import system_heartbeat

        system_heartbeat.apply()
        self.assertIsNotNone(SystemHeartbeat.objects.get(component="celery").last_seen)

    def test_states(self):
        heartbeat("celery", 1)
        self.assertEqual(system_health.evaluate("celery").state, "ok")
        heartbeat("celery", 9)
        self.assertEqual(system_health.evaluate("celery").state, "down")
        self.assertEqual(system_health.evaluate("telegram_bot").state, "off")  # no token on this server
        SystemHeartbeat.objects.filter(component="celery").delete()
        SystemHeartbeat.objects.create(component="celery")
        self.assertEqual(system_health.evaluate("celery").state, "waiting")
        SystemHeartbeat.objects.filter(component="celery").update(created_at=timezone.now() - timedelta(minutes=8))
        self.assertEqual(system_health.evaluate("celery").state, "down")  # never started after the deploy

    def test_one_alert_then_quiet_then_recovery(self):
        heartbeat("celery", 12)
        sent, send = self.watch()
        self.assertEqual(len(sent), 1)
        self.assertIn("Celery worker and Beat", sent[0])
        self.assertIn("sudo makonbook ps", sent[0])
        self.assertTrue(SystemHeartbeat.objects.get(component="celery").alert_open)

        sent, send = self.watch()  # the next minute: no second alert
        self.assertEqual(sent, [])
        send.assert_not_called()

        heartbeat("celery", 0)
        sent, _ = self.watch()
        self.assertEqual(len(sent), 1)
        self.assertIn("Working again: Celery worker and Beat", sent[0])
        self.assertFalse(SystemHeartbeat.objects.get(component="celery").alert_open)

    def test_reminder_every_six_hours(self):
        heartbeat("celery", 30)
        self.watch()
        SystemHeartbeat.objects.filter(component="celery").update(alerted_at=timezone.now() - timedelta(hours=7))
        sent, _ = self.watch()
        self.assertEqual(len(sent), 1)
        self.assertIn("Still down", sent[0])

    def test_an_alert_nobody_received_is_tried_again(self):
        heartbeat("celery", 12)
        with mock.patch.object(system_health, "send_alert", return_value={"delivered": 0}):
            self.assertEqual(system_health.run_watch("web"), [])
        self.assertFalse(SystemHeartbeat.objects.get(component="celery").alert_open)
        sent, _ = self.watch()
        self.assertEqual(len(sent), 1)

    def test_redis_down_is_reported_once_not_celery_too(self):
        self.check_broker.return_value = BROKER_DOWN
        heartbeat("broker", 10)
        heartbeat("celery", 10)
        sent, _ = self.watch()
        self.assertEqual(len(sent), 1)
        self.assertIn("Redis", sent[0])

    def test_alerts_go_to_telegram_admins_and_email(self):
        from django.core import mail

        from apps.telegram_bot.models import TelegramAdmin

        TelegramAdmin.objects.create(telegram_id=111, is_admin=True)
        TelegramAdmin.objects.create(telegram_id=222, is_admin=False, is_support=True)
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token"}), \
                mock.patch.object(system_health, "_send_telegram") as telegram:
            report = system_health.send_alert("hello")
        telegram.assert_called_once_with("111", "hello")
        self.assertEqual(report["delivered"], 2)
        self.assertEqual(mail.outbox[-1].to, ["ops@makonbook.example"])

    def test_bot_watch_checks_the_site(self):
        from apps.telegram_bot.system_watch import watch_once

        with override_settings(SYSTEM_HEALTH_WATCH_ENABLED=True, MONITORING_SITE_CHECK_URL="https://makonbook.example/healthz/"), \
                mock.patch.object(system_health, "check_site", side_effect=lambda: system_health.beat("web")) as site, \
                mock.patch.object(system_health, "send_alert", return_value={"delivered": 1}):
            watch_once()
            self.assertEqual(system_health.evaluate("web").state, "ok")
        site.assert_called_once()
        self.assertTrue(SystemHeartbeat.objects.filter(component="telegram_bot", last_seen__isnull=False).exists())


class HealthzTests(TestCase):
    def test_healthz_answers_without_login(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertEqual(response["Cache-Control"], "no-store")


@override_settings(CELERY_BROKER_URL="redis://127.0.0.1:6399/1", MONITORING_ALERT_EMAILS="", MONITORING_TELEGRAM_CHAT_ID="", HOLLIHOP_ENABLED=False)
class SystemHealthPageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("sh_admin", "admin@makonbook.example", "x")
        broker = mock.patch.object(system_health, "check_broker", return_value=BROKER_OK)
        broker.start()
        self.addCleanup(broker.stop)
        self.url = reverse("admin_system_health")

    def test_admin_sees_every_part_and_the_recipients(self):
        heartbeat("celery", 40, detail={"worker": "celery@web-1"}, alert_open=True)
        self.client.force_login(self.admin)
        page = self.client.get(self.url)
        self.assertContains(page, "System health")
        self.assertContains(page, "Celery worker and Beat")
        self.assertContains(page, "Not working")
        self.assertContains(page, "sudo makonbook ps")
        self.assertContains(page, "admin@makonbook.example")
        self.assertContains(page, "mb102-alert-dot")  # red dot on the sidebar item
        self.assertEqual(page.context["staff_workspace_mode"], "admin")

    def test_others_cannot_open_it(self):
        teacher = User.objects.create_user("sh_teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.post(self.url, {"action": "test"}).status_code, 302)

    def test_send_a_test_alert(self):
        self.client.force_login(self.admin)
        with mock.patch.object(system_health, "send_alert", return_value={"delivered": 1, "telegram_sent": 0, "email_sent": 1, "failed": 0}) as send:
            response = self.client.post(self.url, {"action": "test"}, follow=True)
        send.assert_called_once()
        self.assertContains(response, "Test alert sent")


class WatchMiddlewareTests(TestCase):
    def test_runs_in_the_background_at_most_once_a_minute(self):
        from apps.base.middleware import SystemHealthWatchMiddleware

        SystemHealthWatchMiddleware._next_run = 0.0
        with override_settings(SYSTEM_HEALTH_WATCH_ENABLED=True), mock.patch("threading.Thread") as thread:
            self.client.get("/healthz/")
            self.client.get("/healthz/")
        self.assertEqual(thread.call_count, 1)
        thread.return_value.start.assert_called_once()
        SystemHealthWatchMiddleware._next_run = 0.0
        with mock.patch("threading.Thread") as thread:
            self.client.get("/healthz/")  # off in tests and development
        thread.assert_not_called()

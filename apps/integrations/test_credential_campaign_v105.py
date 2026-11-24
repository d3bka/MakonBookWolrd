"""V105: logins for people the Hollihop import created go out in a controlled campaign."""
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.base.models import UserProfile
from apps.integrations.hollihop import credential_campaign as cc
from apps.integrations.hollihop.sync import HollihopSyncEngine
from apps.integrations.models import CredentialCampaign, HollihopSyncState


def person(username, *, client_id=None, teacher_id=None, phone="+998901234567", status="pending", joined=None, logged_in=False):
    user = User.objects.create_user(username, password="x", first_name=username.title())
    updates = {"hollihop_created": True, "credentials_delivery_status": status, "phone_number": phone,
               "hollihop_client_id": client_id, "hollihop_teacher_id": teacher_id}
    UserProfile.objects.filter(user=user).update(**updates)
    fields = {}
    if joined:
        fields["date_joined"] = joined
    if logged_in:
        fields["last_login"] = timezone.now()
    if fields:
        User.objects.filter(pk=user.pk).update(**fields)
    return User.objects.select_related("profile").get(pk=user.pk)


def fake_delivery(status="sent", sms_error=""):
    def deliver(user, **kwargs):
        UserProfile.objects.filter(user=user).update(credentials_delivery_status=status)
        return SimpleNamespace(overall_status=status, sms_error_safe=sms_error, email_error_safe="",
                               get_sms_status_display=lambda: "Sent" if status == "sent" else "Failed",
                               get_email_status_display=lambda: "Not available")
    return deliver


@override_settings(MAKONBOOK_SMS_PROVIDER="playmobile")
class CampaignTests(TestCase):
    def setUp(self):
        self.completed = timezone.now() - timedelta(hours=2)
        HollihopSyncState.objects.create(provider="hollihop", initial_sync_completed=True, initial_sync_completed_at=self.completed)
        before = self.completed - timedelta(minutes=30)
        self.s1 = person("stu1", client_id=1, joined=before)
        self.s2 = person("stu2", client_id=2, joined=before)
        self.t1 = person("tea1", teacher_id=11, joined=before)
        self.used = person("stu_used", client_id=3, joined=before, logged_in=True)  # already uses MakonBook
        self.done = person("stu_done", client_id=4, joined=before, status="sent")
        self.nophone = person("stu_nophone", client_id=5, joined=before, phone=None)

    def test_who_gets_a_login(self):
        self.assertEqual(set(cc.eligible_users(["students"]).values_list("username", flat=True)), {"stu1", "stu2", "stu_nophone"})
        self.assertEqual(list(cc.eligible_users(["teachers"]).values_list("username", flat=True)), ["tea1"])
        rows = {r["key"]: r for r in cc.overview()}
        self.assertEqual((rows["students"]["total"], rows["students"]["with_phone"], rows["students"]["no_contact"]), (3, 2, 1))

    def test_sync_sends_automatically_only_to_people_created_after_the_import(self):
        engine = HollihopSyncEngine(client=mock.Mock(), send_credentials=True)
        newcomer = person("stu_new", client_id=9, joined=timezone.now())
        with mock.patch("apps.integrations.hollihop.sync.deliver_new_temporary_access") as deliver:
            engine._maybe_send_credentials(self.s1)
            deliver.assert_not_called()  # imported: waits for the campaign
            engine._maybe_send_credentials(newcomer)
            deliver.assert_called_once_with(newcomer)

    def test_each_person_is_sent_once(self):
        with mock.patch.object(cc, "deliver_new_temporary_access", side_effect=fake_delivery()) as deliver:
            self.assertEqual(cc.send_one(self.s1).overall_status, "sent")
            self.assertIsNone(cc.send_one(self.s1))  # a duplicated task finds nothing to do
        deliver.assert_called_once()
        self.assertEqual(cc.send_one(self.nophone), "no_contact")

    def test_batches_until_done_and_pause(self):
        campaign = CredentialCampaign.objects.create(status="running", roles=["students", "teachers"], total=4)
        with mock.patch.object(cc, "BATCH_SIZE", 2), \
                mock.patch.object(cc, "deliver_new_temporary_access", side_effect=fake_delivery()):
            self.assertTrue(cc.run_batch(campaign.pk))
            campaign.refresh_from_db()
            self.assertEqual(campaign.sent, 2)
            CredentialCampaign.objects.filter(pk=campaign.pk).update(status="paused")
            self.assertFalse(cc.run_batch(campaign.pk))  # paused: nothing sent
            campaign.refresh_from_db()
            self.assertEqual(campaign.processed, 2)
            CredentialCampaign.objects.filter(pk=campaign.pk).update(status="running")
            self.assertTrue(cc.run_batch(campaign.pk))
            self.assertFalse(cc.run_batch(campaign.pk))
        campaign.refresh_from_db()
        self.assertEqual((campaign.status, campaign.sent, campaign.no_contact), ("done", 3, 1))
        self.assertEqual(UserProfile.objects.get(user=self.used).credentials_delivery_status, "pending")  # untouched

    def test_failures_are_counted_with_the_error(self):
        campaign = CredentialCampaign.objects.create(status="running", roles=["teachers"], total=1)
        with mock.patch.object(cc, "deliver_new_temporary_access", side_effect=fake_delivery("failed", "PlayMobile: template not approved")):
            cc.run_batch(campaign.pk)
        campaign.refresh_from_db()
        self.assertEqual((campaign.failed, campaign.last_error), (1, "PlayMobile: template not approved"))


@override_settings(MAKONBOOK_SMS_PROVIDER="playmobile")
class CampaignPageTests(TestCase):
    def setUp(self):
        HollihopSyncState.objects.create(provider="hollihop", initial_sync_completed=True, initial_sync_completed_at=timezone.now())
        self.manager = User.objects.create_user("cc_manager", password="x")
        self.manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.s1 = person("stu1", client_id=1, joined=timezone.now() - timedelta(days=1))
        self.s2 = person("stu2", client_id=2, joined=timezone.now() - timedelta(days=1), phone="+998907777777")
        self.url = reverse("hollihop_credential_campaign")
        self.client.force_login(self.manager)

    def test_test_first_then_start_pause_resume_stop(self):
        page = self.client.get(self.url)
        self.assertContains(page, "Send logins")
        self.assertContains(page, "Send a test first")
        self.assertEqual(page.context["staff_workspace_mode"], "manager")

        with mock.patch("apps.integrations.hollihop.tasks.run_credential_campaign_batch.delay") as delay:
            response = self.client.post(self.url, {"action": "start", "roles": ["students"], "confirm": "1"}, follow=True)
            self.assertContains(response, "Send a test to at least one person first")
            delay.assert_not_called()

            with mock.patch.object(cc, "deliver_new_temporary_access", side_effect=fake_delivery()):
                response = self.client.post(self.url, {"action": "test", "roles": ["students"], "people": "+998 90 777 77 77, nobody"}, follow=True)
            self.assertContains(response, "Test · Stu2: sent")
            self.assertContains(response, "“nobody” is not among the people")
            self.assertEqual(UserProfile.objects.get(user=self.s2).credentials_delivery_status, "sent")

            self.client.post(self.url, {"action": "start", "roles": ["students"]})  # no confirmation tick
            delay.assert_not_called()
            self.client.post(self.url, {"action": "start", "roles": ["students"], "confirm": "1"})
            campaign = CredentialCampaign.objects.get()
            self.assertEqual((campaign.status, campaign.total, campaign.roles), ("running", 1, ["students"]))
            delay.assert_called_once_with(campaign.pk)

            self.client.post(self.url, {"action": "pause"})
            self.assertEqual(CredentialCampaign.objects.get().status, "paused")
            self.client.post(self.url, {"action": "resume"})
            self.assertEqual(CredentialCampaign.objects.get().status, "running")
            self.assertEqual(delay.call_count, 2)
            self.client.post(self.url, {"action": "stop"})
            self.assertEqual(CredentialCampaign.objects.get().status, "cancelled")
        self.assertEqual(CredentialCampaign.objects.count(), 1)
        self.client.get(self.url)  # a new draft for later
        self.assertEqual(CredentialCampaign.objects.filter(status="draft").count(), 1)

    def test_teachers_cannot_open_it(self):
        teacher = User.objects.create_user("cc_teacher", password="x")
        teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {"action": "test", "roles": ["students"], "people": "stu1"}).status_code, 403)
        self.assertEqual(UserProfile.objects.get(user=self.s1).credentials_delivery_status, "pending")

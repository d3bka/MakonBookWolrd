"""V112: students who left (or test records) can be removed from "Not delivered"."""
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.base.models import UserProfile
from apps.integrations.hollihop import credential_campaign as cc
from apps.integrations.models import CredentialCampaign, HollihopCredentialDelivery, HollihopSyncLog, HollihopSyncState


@override_settings(MAKONBOOK_SMS_PROVIDER="playmobile")
class DontSendTests(TestCase):
    def setUp(self):
        HollihopSyncState.objects.create(provider="hollihop", initial_sync_completed=True, initial_sync_completed_at=timezone.now())
        manager = User.objects.create_user("v112_manager", password="x")
        manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.client.force_login(manager)
        self.url = reverse("hollihop_credential_campaign")
        CredentialCampaign.objects.create(status="done", roles=["students"], started_at=timezone.now() - timedelta(hours=1))
        self.left = User.objects.create_user("hstu_5439", password="x", first_name="JAVOHIR", last_name="JURABOYEV")
        UserProfile.objects.filter(user=self.left).update(hollihop_created=True, credentials_delivery_status="failed",
                                                          phone_number="+9988701952506", hollihop_client_id=5439)
        HollihopCredentialDelivery.objects.create(user=self.left, overall_status="failed", sms_status="failed")

    def test_dont_send_removes_the_person_for_good(self):
        self.assertContains(self.client.get(self.url), "hstu_5439")
        response = self.client.post(self.url, {"action": "dont_send", "user_id": self.left.pk}, follow=True)
        self.assertContains(response, "Removed from the list")
        self.assertNotContains(response, "hstu_5439")
        self.assertEqual(UserProfile.objects.get(user=self.left).credentials_delivery_status, "not_applicable")
        self.assertTrue(HollihopSyncLog.objects.filter(event_type="credentials_skipped", user=self.left).exists())
        UserProfile.objects.filter(user=self.left).update(phone_number="+998901234567")
        self.assertEqual(cc.retry_candidates(), [])  # never retried
        self.assertFalse(cc.eligible_users(["students"]).filter(pk=self.left.pk).exists())  # never in a campaign

    def test_people_who_already_got_a_login_are_untouched(self):
        UserProfile.objects.filter(user=self.left).update(credentials_delivery_status="sent")
        response = self.client.post(self.url, {"action": "dont_send", "user_id": self.left.pk}, follow=True)
        self.assertContains(response, "This person is not waiting for a login.")
        self.assertEqual(UserProfile.objects.get(user=self.left).credentials_delivery_status, "sent")

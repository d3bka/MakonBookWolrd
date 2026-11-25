"""V111: Uzbek numbers written as 8/0 + 9 digits are accepted; "Not delivered" shows the phone
and "Retry not delivered" sends again once the number was fixed."""
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.base.models import UserProfile
from apps.integrations.hollihop import credential_campaign as cc
from apps.integrations.hollihop.normalization import normalize_phone
from apps.integrations.models import CredentialCampaign, HollihopCredentialDelivery, HollihopSyncState


class PhoneFormatTests(TestCase):
    def test_uzbek_domestic_forms(self):
        self.assertEqual(normalize_phone("8 90 123 45 67"), "+998901234567")
        self.assertEqual(normalize_phone("0 (93) 123-45-67"), "+998931234567")
        self.assertEqual(normalize_phone("+8901234567"), "+998901234567")  # stored by earlier versions
        self.assertEqual(normalize_phone("90 123 45 67"), "+998901234567")
        self.assertEqual(normalize_phone("+998 90 123 45 67"), "+998901234567")

    def test_foreign_numbers_are_kept(self):
        self.assertEqual(normalize_phone("8 916 123 45 67"), "+89161234567")  # Russian 8-prefix: not Uzbek
        self.assertEqual(normalize_phone("+7 916 123 45 67"), "+79161234567")
        self.assertFalse(cc.sms_phone_ok("+7 916 123 45 67"))
        self.assertTrue(cc.sms_phone_ok("8 90 123 45 67"))


@override_settings(MAKONBOOK_SMS_PROVIDER="playmobile")
class RetryTests(TestCase):
    def setUp(self):
        HollihopSyncState.objects.create(provider="hollihop", initial_sync_completed=True, initial_sync_completed_at=timezone.now())
        manager = User.objects.create_user("v111_manager", password="x")
        manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.client.force_login(manager)
        self.url = reverse("hollihop_credential_campaign")
        self.campaign = CredentialCampaign.objects.create(status="done", roles=["students"], started_at=timezone.now() - timedelta(hours=1))
        self.kid = User.objects.create_user("hstu_5875", password="x", first_name="ELDOR", last_name="QOBILJONOV")
        UserProfile.objects.filter(user=self.kid).update(hollihop_created=True, credentials_delivery_status="failed",
                                                         phone_number="+7 916 123 45 67", hollihop_client_id=5875)
        HollihopCredentialDelivery.objects.create(user=self.kid, overall_status="failed", sms_status="failed",
                                                  sms_error_safe="PlayMobile recipient must be a valid Uzbekistan phone number.")

    def test_table_shows_the_phone_and_retry_waits_for_a_fix(self):
        page = self.client.get(self.url)
        self.assertContains(page, "+7 916 123 45 67")
        self.assertContains(page, "Retry not delivered (0)")
        response = self.client.post(self.url, {"action": "retry_failed"}, follow=True)
        self.assertContains(response, "Nobody in “Not delivered” can be reached yet")

        UserProfile.objects.filter(user=self.kid).update(phone_number="+998901234567")  # fixed in Hollihop, synced
        page = self.client.get(self.url)
        self.assertContains(page, "fixed · can retry")
        self.assertContains(page, "Retry not delivered (1)")

        def deliver(user, **kwargs):
            UserProfile.objects.filter(user=user).update(credentials_delivery_status="sent")
            return SimpleNamespace(overall_status="sent", sms_error_safe="", email_error_safe="")

        with mock.patch.object(cc, "deliver_new_temporary_access", side_effect=deliver) as send:
            response = self.client.post(self.url, {"action": "retry_failed"}, follow=True)
        send.assert_called_once()
        self.assertContains(response, "Sent again: 1 delivered, 0 still failed.")
        self.assertNotContains(response, "hstu_5875")  # delivered now: gone from "Not delivered"

    def test_people_who_logged_in_are_never_retried(self):
        UserProfile.objects.filter(user=self.kid).update(phone_number="+998901234567")
        User.objects.filter(pk=self.kid.pk).update(last_login=timezone.now())
        self.assertEqual(cc.retry_candidates(self.campaign.started_at), [])

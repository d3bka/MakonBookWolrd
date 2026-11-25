"""V110: Send logins — invalid phones counted up front, a sample login SMS to the manager's
own phone unlocks sending, and "Not delivered" lists each person once."""
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.base.models import UserProfile
from apps.integrations.hollihop import credential_campaign as cc
from apps.integrations.hollihop.sms import SmsDeliveryError, SmsSendResult
from apps.integrations.models import CredentialCampaign, HollihopCredentialDelivery, HollihopSyncState


def student(username, phone, email=""):
    user = User.objects.create_user(username, email=email, password="x", first_name=username)
    UserProfile.objects.filter(user=user).update(hollihop_created=True, credentials_delivery_status="pending",
                                                 phone_number=phone, hollihop_client_id=abs(hash(username)) % 10**8)
    return user


@override_settings(MAKONBOOK_SMS_PROVIDER="playmobile")
class SendLoginsV110Tests(TestCase):
    def setUp(self):
        HollihopSyncState.objects.create(provider="hollihop", initial_sync_completed=True, initial_sync_completed_at=timezone.now())
        self.manager = User.objects.create_user("v110_manager", password="x", first_name="Dilnoza")
        self.manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.client.force_login(self.manager)
        self.url = reverse("hollihop_credential_campaign")

    def test_invalid_phones_are_counted_separately(self):
        student("ok_local", "901234567")
        student("ok_full", "+998 90 765 43 21")
        student("bad_foreign", "+7 916 123 45 67")
        student("bad_but_email", "+7 916 000 00 00", email="kid@makonbook.example")
        student("none", None)
        rows = {r["key"]: r for r in cc.overview()}["students"]
        self.assertEqual((rows["total"], rows["with_phone"], rows["invalid_phone"], rows["email_only"], rows["no_contact"]),
                         (5, 2, 1, 1, 1))
        self.assertTrue(cc.sms_phone_ok("90 123 45 67"))
        self.assertFalse(cc.sms_phone_ok("123"))

    def test_sample_login_sms_to_my_phone_unlocks_sending(self):
        sent = SmsSendResult(provider="playmobile", message_id="mb1")
        with mock.patch("apps.integrations.hollihop.sms.send_sms", return_value=sent) as send:
            response = self.client.post(self.url, {"action": "sample", "roles": ["students"], "sample_phone": "+998901112233"}, follow=True)
        self.assertContains(response, "Sample login SMS accepted by playmobile")
        phone, text = send.call_args.args
        self.assertEqual(phone, "+998901112233")
        self.assertIn("Salom, Dilnoza!", text)
        self.assertIn("Login: namuna.login", text)
        self.assertEqual(send.call_args.kwargs["template_variables"]["Login"], "namuna.login")
        self.assertEqual(CredentialCampaign.objects.get().test_sent_ok, 1)
        self.assertNotContains(response, 'title="Send a test first"')  # Start sending is enabled
        self.assertTrue(User.objects.get(pk=self.manager.pk).check_password("x"))  # nobody's password changed

    def test_failed_sample_does_not_unlock(self):
        with mock.patch("apps.integrations.hollihop.sms.send_sms", side_effect=SmsDeliveryError("PlayMobile rejected the text")):
            response = self.client.post(self.url, {"action": "sample", "roles": ["students"], "sample_phone": "+998901112233"}, follow=True)
        self.assertContains(response, "Sample login SMS failed: PlayMobile rejected the text")
        self.assertEqual(CredentialCampaign.objects.get().test_sent_ok, 0)

    def test_not_delivered_lists_each_person_once(self):
        self.client.get(self.url)  # creates the draft campaign
        CredentialCampaign.objects.update(created_at=timezone.now() - timedelta(hours=1))
        kid = student("kid", "+7 916 123 45 67")
        UserProfile.objects.filter(user=kid).update(credentials_delivery_status="failed")  # as after a failed delivery
        for _ in range(3):
            HollihopCredentialDelivery.objects.create(user=kid, overall_status="failed", sms_status="failed",
                                                      sms_error_safe="PlayMobile recipient must be a valid Uzbekistan phone number.")
        page = self.client.get(self.url)
        self.assertEqual(len(page.context["recent_failures"]), 1)

"""V112: Hollihop statuses of students who left; one row per person; no double resend."""
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.base.models import UserProfile
from apps.integrations.hollihop.sync import HollihopSyncEngine
from apps.integrations.models import HollihopCredentialDelivery


from satmakon import settings as project_settings

DEFAULT_INACTIVE = project_settings._status_set(project_settings.HOLLIHOP_INACTIVE_STUDENT_STATUSES_DEFAULT.split(","))


@override_settings(HOLLIHOP_INACTIVE_STUDENT_STATUSES=DEFAULT_INACTIVE)  # independent of the local .env
class StatusTests(TestCase):
    def test_left_and_paused_statuses_are_inactive(self):
        state = HollihopSyncEngine._student_active_state
        for status in ("Ушел (после пробного урока)", "Ушёл (старый ученик)", "Отложил обучение", "Закончил обучение"):
            self.assertIs(state(status), False, status)
        self.assertIs(state("Занимается"), True)
        self.assertIsNone(state("[Нет]"))
        self.assertIn("ушел (после пробного урока)", settings.HOLLIHOP_INACTIVE_STUDENT_STATUSES)


class DashboardTests(TestCase):
    def setUp(self):
        manager = User.objects.create_user("v112d_manager", password="x")
        manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.client.force_login(manager)
        self.kid = User.objects.create_user("hstu_5875", password="x", first_name="ELDOR")
        UserProfile.objects.filter(user=self.kid).update(hollihop_created=True, credentials_delivery_status="failed",
                                                         phone_number="+99887729677", hollihop_client_id=5875)
        for _ in range(3):
            HollihopCredentialDelivery.objects.create(user=self.kid, overall_status="failed", sms_status="failed")
        self.done = User.objects.create_user("hstu_6273", password="x", first_name="ZIYODULLA")
        UserProfile.objects.filter(user=self.done).update(hollihop_created=True, credentials_delivery_status="partial",
                                                          hollihop_client_id=6273)
        HollihopCredentialDelivery.objects.create(user=self.done, overall_status="partial", sms_status="failed", email_status="sent")

    def test_one_row_per_person_still_waiting(self):
        page = self.client.get(reverse("hollihop_dashboard"))
        rows = page.context["failed_deliveries"]
        self.assertEqual([d.user_id for d in rows], [self.kid.pk])  # once; the e-mail one got the login

    def test_resend_is_blocked_for_ten_minutes_after_a_sending(self):
        UserProfile.objects.filter(user=self.done).update(credentials_delivery_status="sent")
        HollihopCredentialDelivery.objects.create(user=self.done, overall_status="sent", sms_status="sent")
        url = reverse("hollihop_resend_credentials", args=[self.done.pk])
        with mock.patch("apps.integrations.hollihop.views.deliver_new_temporary_access") as deliver:
            response = self.client.post(url, {"confirm": "RESET"}, follow=True)
            deliver.assert_not_called()
            self.assertContains(response, "A login was already sent")
            HollihopCredentialDelivery.objects.filter(user=self.done).update(created_at=timezone.now() - timedelta(minutes=11))
            deliver.return_value = mock.Mock(overall_status="sent")
            self.client.post(url, {"confirm": "RESET"})
            deliver.assert_called_once()

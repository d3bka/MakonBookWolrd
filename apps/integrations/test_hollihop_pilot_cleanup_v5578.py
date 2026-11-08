from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.integrations.management.commands.pilot_hollihop_user import PilotIdentity
from apps.integrations.models import HollihopCredentialDelivery, HollihopSyncLog, HollihopSyncState


BASE = dict(
    SCHOOL_DATA_PROVIDER="local",
    HOLLIHOP_ENABLED=True,
    HOLLIHOP_PILOT_ENABLED=True,
    HOLLIHOP_PILOT_TARGETS="manager:12557",
    HOLLIHOP_API_URL="https://example.invalid/Api/V2",
    HOLLIHOP_AUTH_KEY="test-key",
)


def identity():
    return PilotIdentity(
        kind="manager",
        requested_id=12557,
        external_id=12557,
        payload={"Id": 12557, "FirstName": "Pilot", "LastName": "Manager", "Mobile": "+998901234567"},
    )


@override_settings(**BASE)
class HollihopPilotCleanupV5578Tests(TestCase):
    @patch("apps.integrations.management.commands.cleanup_hollihop_pilot.HollihopClient")
    @patch("apps.integrations.management.commands.cleanup_hollihop_pilot._detect_identity")
    def test_dry_run_does_not_delete_pilot_user(self, detect, client):
        detect.return_value = identity()
        user = User.objects.create_user("hmanager_12557")
        p = user.profile
        p.hollihop_created = True
        p.hollihop_employee_id = 12557
        p.save()

        out = StringIO()
        call_command("cleanup_hollihop_pilot", stdout=out)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assertIn("DRY RUN only", out.getvalue())

    @patch("apps.integrations.management.commands.cleanup_hollihop_pilot.HollihopClient")
    @patch("apps.integrations.management.commands.cleanup_hollihop_pilot._detect_identity")
    def test_apply_deletes_only_hollihop_created_user_and_metadata(self, detect, client):
        detect.return_value = identity()
        user = User.objects.create_user("hmanager_12557")
        p = user.profile
        p.hollihop_created = True
        p.hollihop_employee_id = 12557
        p.save()
        HollihopCredentialDelivery.objects.create(user=user)
        HollihopSyncLog.objects.create(event_type="manager_created", entity_type="manager", external_id="12557", user=user)

        call_command("cleanup_hollihop_pilot", "--apply", stdout=StringIO())
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        self.assertEqual(HollihopCredentialDelivery.objects.count(), 0)
        self.assertEqual(HollihopSyncLog.objects.count(), 0)

    @patch("apps.integrations.management.commands.cleanup_hollihop_pilot.HollihopClient")
    @patch("apps.integrations.management.commands.cleanup_hollihop_pilot._detect_identity")
    def test_existing_makonbook_user_is_preserved(self, detect, client):
        detect.return_value = identity()
        user = User.objects.create_user("existing")
        p = user.profile
        p.hollihop_created = False
        p.hollihop_employee_id = 12557
        p.save()
        HollihopCredentialDelivery.objects.create(user=user)

        call_command("cleanup_hollihop_pilot", "--apply", stdout=StringIO())
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assertEqual(HollihopCredentialDelivery.objects.count(), 0)

    @patch("apps.integrations.management.commands.cleanup_hollihop_pilot.HollihopClient")
    @patch("apps.integrations.management.commands.cleanup_hollihop_pilot._detect_identity")
    def test_reset_state_is_explicit(self, detect, client):
        detect.return_value = identity()
        HollihopSyncState.objects.create(provider="hollihop")
        call_command("cleanup_hollihop_pilot", "--apply", "--reset-state", stdout=StringIO())
        self.assertFalse(HollihopSyncState.objects.filter(provider="hollihop").exists())

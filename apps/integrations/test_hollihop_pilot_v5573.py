from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.integrations.hollihop.sync import SyncSummary


User = get_user_model()


BASE = dict(
    HOLLIHOP_ENABLED=True,
    SCHOOL_DATA_PROVIDER="local",
    HOLLIHOP_API_URL="https://example.t8s.ru/Api/V2",
    HOLLIHOP_AUTH_KEY="x" * 64,
    HOLLIHOP_PILOT_ENABLED=True,
    HOLLIHOP_PILOT_TARGETS="",
    HOLLIHOP_PILOT_USER_IDS=(12557,),
    HOLLIHOP_PILOT_USER_ID=12557,
    HOLLIHOP_PILOT_KIND="auto",
    HOLLIHOP_PILOT_SEND_SMS=False,
)


class HollihopPilotV5573Tests(TestCase):
    @override_settings(**{**BASE, "HOLLIHOP_PILOT_ENABLED": False})
    def test_pilot_requires_explicit_enable(self):
        with self.assertRaisesMessage(CommandError, "Pilot mode is disabled"):
            call_command("pilot_hollihop_user", "--dry-run")

    @override_settings(**{**BASE, "SCHOOL_DATA_PROVIDER": "hollihop"})
    def test_pilot_refuses_full_provider_mode(self):
        with self.assertRaisesMessage(CommandError, "requires SCHOOL_DATA_PROVIDER=local"):
            call_command("pilot_hollihop_user", "--dry-run")

    @override_settings(**BASE)
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopSyncEngine")
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopClient")
    def test_auto_detects_manager_employee_in_dry_run(self, client_cls, engine_cls):
        client = client_cls.return_value
        client.get_students.return_value = []
        client.get_teachers.return_value = []
        client.get_employees.return_value = [{
            "Id": 12557, "FirstName": "Islom", "LastName": "Baxtiyorov",
            "Mobile": "+998971975838", "Status": "Работает",
        }]
        engine = engine_cls.return_value
        engine._employee_is_manager.return_value = True
        output = StringIO()
        call_command("pilot_hollihop_user", "--dry-run", stdout=output)
        self.assertIn("Detected type: manager", output.getvalue())
        self.assertIn("+998971975838", output.getvalue())
        engine.sync_managers.assert_not_called()

    @override_settings(**BASE)
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopSyncEngine")
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopClient")
    def test_auto_refuses_ambiguous_same_numeric_id(self, client_cls, engine_cls):
        client = client_cls.return_value
        client.get_students.return_value = [{"Id": 12557, "ClientId": 70001}]
        client.get_teachers.return_value = [{"Id": 12557}]
        client.get_employees.return_value = []
        with self.assertRaisesMessage(CommandError, "multiple identity namespaces"):
            call_command("pilot_hollihop_user", "--dry-run")

    @override_settings(**{**BASE, "HOLLIHOP_PILOT_KIND": "teacher"})
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopSyncEngine")
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopClient")
    def test_forced_teacher_queries_only_teacher_namespace(self, client_cls, engine_cls):
        client = client_cls.return_value
        client.get_teachers.return_value = [{"Id": 12557, "FirstName": "Teacher"}]
        output = StringIO()
        call_command("pilot_hollihop_user", "--dry-run", stdout=output)
        client.get_students.assert_not_called()
        client.get_employees.assert_not_called()
        self.assertIn("Detected type: teacher", output.getvalue())

    @override_settings(**{
        **BASE,
        "HOLLIHOP_PILOT_KIND": "student",
        "HOLLIHOP_PILOT_SEND_SMS": True,
        "MAKONBOOK_SMS_PROVIDER": "playmobile",
    })
    @patch("apps.integrations.management.commands.pilot_hollihop_user.deliver_new_temporary_access")
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopSyncEngine")
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopClient")
    def test_live_new_student_translates_ui_id_to_client_id_and_sends_sms_only(self, client_cls, engine_cls, deliver):
        client = client_cls.return_value
        client.get_students.return_value = [{
            "Id": 12557,
            "ClientId": 70001,
            "FirstName": "Pilot",
            "LastName": "Student",
            "Mobile": "+998901234567",
            "Status": "Занимается",
        }]
        engine = engine_cls.return_value
        engine.summary = SyncSummary()

        user = User.objects.create_user(username="hstu_70001")
        profile = user.profile
        profile.hollihop_client_id = 70001
        profile.hollihop_created = True
        profile.phone_number = "+998901234567"
        profile.credentials_delivery_status = "pending"
        profile.save()

        class Delivery:
            sms_status = "sent"
            overall_status = "sent"
        deliver.return_value = Delivery()

        output = StringIO()
        call_command("pilot_hollihop_user", stdout=output)
        client.get_students.assert_called_with(student_id=12557)
        engine.sync_students.assert_called_once_with(only_client_id=70001)
        engine.sync_teachers.assert_not_called()
        engine.sync_managers.assert_not_called()
        deliver.assert_called_once_with(user, channels={"sms"}, sms_role_label="Student")
        self.assertIn("Hollihop Student ID: 12557", output.getvalue())
        self.assertIn("Hollihop ClientId: 70001", output.getvalue())
        self.assertIn("Credential SMS sent", output.getvalue())

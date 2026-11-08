from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings


BASE = dict(
    HOLLIHOP_ENABLED=True,
    SCHOOL_DATA_PROVIDER="local",
    HOLLIHOP_API_URL="https://example.t8s.ru/Api/V2",
    HOLLIHOP_AUTH_KEY="x" * 64,
    HOLLIHOP_PILOT_ENABLED=True,
    HOLLIHOP_PILOT_TARGETS="student:37,manager:12557,student:8",
    HOLLIHOP_PILOT_USER_IDS=(),
    HOLLIHOP_PILOT_USER_ID=0,
    HOLLIHOP_PILOT_KIND="auto",
    HOLLIHOP_PILOT_SEND_SMS=False,
)


class HollihopPilotV5576Tests(TestCase):
    @override_settings(**BASE)
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopSyncEngine")
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopClient")
    def test_student_ui_id_is_not_client_id(self, client_cls, engine_cls):
        client = client_cls.return_value

        def students(*, student_id):
            if student_id == 37:
                return [{"Id": 37, "ClientId": 9037, "FirstName": "ISLOM", "LastName": "BAHTIYOROV"}]
            if student_id == 8:
                return [{"Id": 8, "ClientId": 9008, "FirstName": "RAHIMOVA", "LastName": "NIGINABONU"}]
            return []

        client.get_students.side_effect = students
        client.get_employees.return_value = [{"Id": 12557, "FirstName": "Islom", "LastName": "Baxtiyorov"}]
        engine_cls.return_value._employee_is_manager.return_value = True

        output = StringIO()
        call_command("pilot_hollihop_user", "--dry-run", stdout=output)
        text = output.getvalue()
        self.assertIn("Name: ISLOM BAHTIYOROV", text)
        self.assertIn("Hollihop Student ID: 37", text)
        self.assertIn("Hollihop ClientId: 9037", text)
        self.assertIn("Name: RAHIMOVA NIGINABONU", text)
        client.get_students.assert_any_call(student_id=37)
        client.get_students.assert_any_call(student_id=8)
        client.get_teachers.assert_not_called()

    @override_settings(**{**BASE, "HOLLIHOP_PILOT_TARGETS": "student:4"})
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopSyncEngine")
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopClient")
    def test_typed_target_avoids_cross_namespace_ambiguity(self, client_cls, engine_cls):
        client = client_cls.return_value
        client.get_students.return_value = [{"Id": 4, "ClientId": 4004, "FirstName": "Student Four"}]
        output = StringIO()
        call_command("pilot_hollihop_user", "--dry-run", stdout=output)
        self.assertIn("Detected type: student", output.getvalue())
        client.get_students.assert_called_once_with(student_id=4)
        client.get_teachers.assert_not_called()
        client.get_employees.assert_not_called()

    @override_settings(**{**BASE, "HOLLIHOP_PILOT_TARGETS": "auto:37"})
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopSyncEngine")
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopClient")
    def test_wrong_student_row_is_never_accepted(self, client_cls, engine_cls):
        client = client_cls.return_value
        # Simulates the old bug: a query intended for 37 returns student Id 59.
        client.get_students.return_value = [{"Id": 59, "ClientId": 37, "FirstName": "AKMAL"}]
        client.get_teachers.return_value = []
        client.get_employees.return_value = []
        with self.assertRaisesMessage(CommandError, "No supported Hollihop"):
            call_command("pilot_hollihop_user", "--dry-run")

    @override_settings(**{**BASE, "HOLLIHOP_PILOT_TARGETS": "auto:4"})
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopSyncEngine")
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopClient")
    def test_real_namespace_collision_requires_typed_target(self, client_cls, engine_cls):
        client = client_cls.return_value
        client.get_students.return_value = [{"Id": 4, "ClientId": 4004}]
        client.get_teachers.return_value = [{"Id": 4}]
        client.get_employees.return_value = []
        with self.assertRaisesMessage(CommandError, "HOLLIHOP_PILOT_TARGETS"):
            call_command("pilot_hollihop_user", "--dry-run")

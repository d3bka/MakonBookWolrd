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
    HOLLIHOP_PILOT_TARGETS="",
    HOLLIHOP_PILOT_USER_IDS=(4, 12557, 37),
    HOLLIHOP_PILOT_USER_ID=4,
    HOLLIHOP_PILOT_KIND="auto",
    HOLLIHOP_PILOT_SEND_SMS=False,
)


class HollihopPilotV5574Tests(TestCase):
    @override_settings(**BASE)
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopSyncEngine")
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopClient")
    def test_dry_run_processes_multiple_ids_in_order(self, client_cls, engine_cls):
        client = client_cls.return_value

        def students(*, student_id):
            if student_id == 4:
                return [{"Id": 4, "ClientId": 4004, "FirstName": "Student", "Mobile": "+998901111111"}]
            return []

        def teachers(*, teacher_id):
            if teacher_id == 37:
                return [{"Id": 37, "FirstName": "Teacher", "Mobile": "+998902222222"}]
            return []

        def employees(*, employee_id, corporative=None):
            if employee_id == 12557:
                return [{"Id": 12557, "FirstName": "Manager", "Mobile": "+998903333333"}]
            return []

        client.get_students.side_effect = students
        client.get_teachers.side_effect = teachers
        client.get_employees.side_effect = employees
        engine_cls.return_value._employee_is_manager.return_value = True

        output = StringIO()
        call_command("pilot_hollihop_user", "--dry-run", stdout=output)
        text = output.getvalue()
        self.assertIn("Configured targets: 4, 12557, 37", text)
        self.assertIn("[1/3] Hollihop target 4", text)
        self.assertIn("[2/3] Hollihop target 12557", text)
        self.assertIn("[3/3] Hollihop target 37", text)
        self.assertIn("Successful: 3", text)
        self.assertIn("Errors: 0", text)

    @override_settings(**BASE)
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopSyncEngine")
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopClient")
    def test_bad_middle_id_does_not_prevent_later_id_from_being_checked(self, client_cls, engine_cls):
        client = client_cls.return_value

        def students(*, student_id):
            if student_id in {4, 37}:
                return [{"Id": student_id, "ClientId": 10000 + student_id, "FirstName": f"Student{student_id}"}]
            return []

        client.get_students.side_effect = students
        client.get_teachers.return_value = []
        client.get_employees.return_value = []
        engine_cls.return_value._employee_is_manager.return_value = False

        output = StringIO()
        errors = StringIO()
        with self.assertRaisesMessage(CommandError, "1 target(s) failed"):
            call_command("pilot_hollihop_user", "--dry-run", stdout=output, stderr=errors)
        self.assertIn("[3/3] Hollihop target 37", output.getvalue())
        self.assertIn("Target 12557", errors.getvalue())
        self.assertIn("Successful: 2", output.getvalue())
        self.assertIn("Errors: 1", output.getvalue())

    @override_settings(**{**BASE, "HOLLIHOP_PILOT_USER_IDS": (), "HOLLIHOP_PILOT_USER_ID": "4,12557,37"})
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopSyncEngine")
    @patch("apps.integrations.management.commands.pilot_hollihop_user.HollihopClient")
    def test_legacy_singular_setting_accepts_comma_separated_ids(self, client_cls, engine_cls):
        client = client_cls.return_value
        client.get_students.side_effect = lambda student_id: [{"Id": student_id, "ClientId": 20000 + student_id, "FirstName": "Pilot"}]
        client.get_teachers.return_value = []
        client.get_employees.return_value = []
        output = StringIO()
        call_command("pilot_hollihop_user", "--dry-run", stdout=output)
        self.assertIn("Configured targets: 4, 12557, 37", output.getvalue())

    @override_settings(**{**BASE, "SCHOOL_DATA_PROVIDER": "hollihop"})
    def test_batch_still_refuses_full_provider_mode(self):
        with self.assertRaisesMessage(CommandError, "requires SCHOOL_DATA_PROVIDER=local"):
            call_command("pilot_hollihop_user", "--dry-run")

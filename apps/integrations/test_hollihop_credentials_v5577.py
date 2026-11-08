from __future__ import annotations

import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.integrations.hollihop.credentials import (
    deliver_new_temporary_access,
    generate_temporary_password,
)
from apps.integrations.hollihop.sms import SmsSendResult


User = get_user_model()


class HollihopCredentialV5577Tests(TestCase):
    def test_temporary_password_is_readable_4_plus_4_format(self):
        for _ in range(50):
            password = generate_temporary_password()
            self.assertRegex(password, r"^[ABCDEFGHJKMNPQRSTUVWXYZ]{4}-[23456789]{4}$")
            self.assertFalse(re.search(r"[ILO01]", password))

    @override_settings(
        MAKONBOOK_SMS_PROVIDER="playmobile",
        SITE_URL="https://makonbook.uz",
    )
    @patch("apps.integrations.hollihop.credentials.generate_temporary_password", return_value="KRMH-5837")
    @patch("apps.integrations.hollihop.credentials.send_sms")
    def test_student_sms_is_friendly_and_contains_readable_password(self, send_sms, _password):
        send_sms.return_value = SmsSendResult(provider="playmobile", message_id="mb-test", status="accepted")
        user = User.objects.create_user(username="hstu_777", first_name="Islom")
        profile = user.profile
        profile.hollihop_client_id = 777
        profile.hollihop_created = True
        profile.phone_number = "+998901234567"
        profile.credentials_delivery_status = "pending"
        profile.save()

        delivery = deliver_new_temporary_access(user, channels={"sms"})

        self.assertEqual(delivery.sms_status, "sent")
        phone, text = send_sms.call_args.args
        self.assertEqual(phone, "+998901234567")
        self.assertIn("Salom, Islom!", text)
        self.assertIn("MakonBook student akkauntingiz tayyor.", text)
        self.assertIn("Login: +998901234567", text)
        self.assertIn("Vaqtinchalik parol: KRMH-5837", text)
        self.assertIn("Kirish: https://makonbook.uz/login/", text)
        self.assertIn("Birinchi kirishda parolni yangilang.", text)
        self.assertEqual(send_sms.call_args.kwargs["template_variables"]["staff_type"], "student")

        user.refresh_from_db()
        self.assertTrue(user.check_password("KRMH-5837"))
        self.assertTrue(user.profile.must_change_password)

    @override_settings(
        MAKONBOOK_SMS_PROVIDER="playmobile",
        SITE_URL="https://makonbook.uz",
    )
    @patch("apps.integrations.hollihop.credentials.generate_temporary_password", return_value="NPKR-7264")
    @patch("apps.integrations.hollihop.credentials.send_sms")
    def test_teacher_sms_uses_teacher_label(self, send_sms, _password):
        send_sms.return_value = SmsSendResult(provider="playmobile", message_id="mb-test", status="accepted")
        user = User.objects.create_user(username="hteacher_88", first_name="Xasan")
        profile = user.profile
        profile.hollihop_teacher_id = 88
        profile.hollihop_created = True
        profile.phone_number = "+998901234568"
        profile.credentials_delivery_status = "pending"
        profile.save()

        deliver_new_temporary_access(user, channels={"sms"})
        text = send_sms.call_args.args[1]
        self.assertIn("MakonBook teacher akkauntingiz tayyor.", text)

    @override_settings(
        MAKONBOOK_SMS_PROVIDER="playmobile",
        SITE_URL="https://makonbook.uz",
    )
    @patch("apps.integrations.hollihop.credentials.generate_temporary_password", return_value="TRMK-8357")
    @patch("apps.integrations.hollihop.credentials.send_sms")
    def test_manager_sms_uses_manager_label(self, send_sms, _password):
        send_sms.return_value = SmsSendResult(provider="playmobile", message_id="mb-test", status="accepted")
        user = User.objects.create_user(username="hmanager_12557", first_name="Islom")
        profile = user.profile
        profile.hollihop_employee_id = 12557
        profile.hollihop_created = True
        profile.phone_number = "+998901234569"
        profile.credentials_delivery_status = "pending"
        profile.save()

        deliver_new_temporary_access(user, channels={"sms"})
        text = send_sms.call_args.args[1]
        self.assertIn("MakonBook manager akkauntingiz tayyor.", text)

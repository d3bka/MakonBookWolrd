from __future__ import annotations

from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from django.contrib.auth import get_user_model
from apps.integrations.hollihop.credentials import _build_sms_text, _sms_template_values
from apps.integrations.hollihop.sms import _send_playmobile, SmsDeliveryError


class PlayMobileTemplateV631Tests(SimpleTestCase):
    @override_settings(SITE_URL="https://makonbook.uz")
    def test_uzbek_credential_template_exact_text(self):
        # UserProfile is a relation in production; supply a basic profile stub.
        class FakeUser:
            first_name = 'Ali'
            profile = type('Profile', (), {'hollihop_client_id': 37, 'hollihop_teacher_id': None, 'hollihop_employee_id': None})()
            def get_username(self): return 'ali37'
        user = FakeUser()
        text = _build_sms_text(user, login_value='ali37', temporary_password='ABCD-2345', sms_role_label='student')
        self.assertEqual(text, 'Salom, Ali! MakonBook student akkauntingiz tayyor.\nLogin: ali37\nVaqtinchalik parol: ABCD-2345\nKirish: https://makonbook.uz/login/\nBirinchi kirishda parolni yangilang.')
        self.assertEqual(set(_sms_template_values(user, login_value='ali37', temporary_password='ABCD-2345', sms_role_label='student')), {'name', 'staff_type', 'Login', 'password', 'website'})

    @override_settings(PLAYMOBILE_API_URL='https://send.smsxabar.uz/broker-api/send', PLAYMOBILE_LOGIN='test', PLAYMOBILE_PASSWORD='test', PLAYMOBILE_ORIGINATOR='SATMAKON', PLAYMOBILE_TEMPLATE_ID='42')
    @patch('apps.integrations.hollihop.sms._post_json_text', return_value='Request is received')
    def test_template_request_uses_variables_not_conflicting_text(self, post):
        vars = {'name':'Ali','staff_type':'student','Login':'ali37','password':'ABCD-2345','website':'https://makonbook.uz/login/'}
        _send_playmobile('+998901234567', 'placeholder text', template_variables=vars)
        request = post.call_args.args[1]['messages'][0]
        self.assertEqual(request['template-id'], '42')
        self.assertEqual(request['variables'], vars)
        self.assertNotIn('sms', request)

    @override_settings(PLAYMOBILE_API_URL='https://send.smsxabar.uz/broker-api/send', PLAYMOBILE_LOGIN='test', PLAYMOBILE_PASSWORD='test', PLAYMOBILE_ORIGINATOR='SATMAKON', PLAYMOBILE_TEMPLATE_ID='')
    @patch('apps.integrations.hollihop.sms._post_json_text', return_value='Request is received')
    def test_plain_text_request_is_unchanged(self, post):
        _send_playmobile('+998901234567', 'Salom, Ali!')
        request = post.call_args.args[1]['messages'][0]
        self.assertEqual(request['sms']['content']['text'], 'Salom, Ali!')
        self.assertNotIn('template-id', request)

    @override_settings(PLAYMOBILE_API_URL='https://send.smsxabar.uz/broker-api/send', PLAYMOBILE_LOGIN='test', PLAYMOBILE_PASSWORD='test', PLAYMOBILE_ORIGINATOR='SATMAKON', PLAYMOBILE_TEMPLATE_ID='42')
    def test_refuses_generic_text_if_template_id_is_active(self):
        with self.assertRaises(SmsDeliveryError):
            _send_playmobile('+998901234567', 'Wrong body')

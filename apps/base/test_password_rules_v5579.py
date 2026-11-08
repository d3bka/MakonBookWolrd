from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse


class TemporaryPasswordLiveRulesV5579Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="islom.baxtiyorov",
            first_name="Islom",
            last_name="Baxtiyorov",
            email="islom@example.com",
            password="Temporary-9274",
        )
        self.user.profile.must_change_password = True
        self.user.profile.save(update_fields=["must_change_password", "updated_at"])
        self.client.force_login(self.user)

    def test_template_has_live_rule_markers_and_endpoint(self):
        html = render_to_string(
            "base/change_temporary_password.html",
            {"form": SetPasswordForm(self.user)},
        )
        self.assertIn('data-password-rule="similarity"', html)
        self.assertIn('data-password-rule="length"', html)
        self.assertIn('data-password-rule="common"', html)
        self.assertIn('data-password-rule="numeric"', html)
        self.assertIn('data-password-rules-url=', html)
        self.assertIn("validateWithServer", html)

    def test_rule_endpoint_uses_real_django_validators(self):
        response = self.client.post(
            reverse("temporary_password_rules"),
            {"password": "V7p!Kx9#Qm2"},
        )
        self.assertEqual(response.status_code, 200)
        rules = response.json()["rules"]
        self.assertEqual(set(rules), {"similarity", "length", "common", "numeric"})
        self.assertTrue(all(rules.values()))

    def test_numeric_password_is_marked_invalid_for_numeric_rule(self):
        response = self.client.post(
            reverse("temporary_password_rules"),
            {"password": "12345678"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["rules"]["numeric"])

    def test_similar_password_is_marked_invalid_for_similarity_rule(self):
        response = self.client.post(
            reverse("temporary_password_rules"),
            {"password": "islom.baxtiyorov2026"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["rules"]["similarity"])

    def test_endpoint_refuses_user_without_temporary_password_requirement(self):
        self.user.profile.must_change_password = False
        self.user.profile.save(update_fields=["must_change_password", "updated_at"])
        response = self.client.post(
            reverse("temporary_password_rules"),
            {"password": "V7p!Kx9#Qm2"},
        )
        self.assertEqual(response.status_code, 403)

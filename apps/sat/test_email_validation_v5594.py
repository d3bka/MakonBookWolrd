from django.test import SimpleTestCase

from .event_registration import (
    EmailValidationError,
    assess_registration_email,
    validate_registration_email,
)


class MockRegistrationEmailValidationV5594Tests(SimpleTestCase):
    def test_valid_gmail_address_passes(self):
        self.assertEqual(validate_registration_email("Student@Gmail.com"), "student@gmail.com")

    def test_gml_co_is_flagged_as_probable_gmail_typo(self):
        assessment = assess_registration_email("student@gml.co")
        self.assertEqual(assessment.status, "suspicious")
        self.assertEqual(assessment.suggested_email, "student@gmail.com")
        with self.assertRaises(EmailValidationError) as raised:
            validate_registration_email("student@gml.co")
        self.assertEqual(raised.exception.code, "suspicious_email")
        self.assertTrue(raised.exception.can_override)

    def test_suspicious_address_can_be_explicitly_overridden(self):
        self.assertEqual(
            validate_registration_email("student@gml.co", allow_suspicious=True),
            "student@gml.co",
        )

    def test_invalid_syntax_is_blocked_and_cannot_be_overridden(self):
        with self.assertRaises(EmailValidationError) as raised:
            validate_registration_email("not-an-email", allow_suspicious=True)
        self.assertEqual(raised.exception.code, "invalid_email")
        self.assertFalse(raised.exception.can_override)

    def test_custom_school_domain_is_not_auto_changed(self):
        assessment = assess_registration_email("student@school-example.uz")
        self.assertEqual(assessment.status, "valid")
        self.assertEqual(assessment.suggested_email, "")

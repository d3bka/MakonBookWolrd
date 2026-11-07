"""Hollihop error reporting never exposes exception text or secrets."""
import unittest

from apps.integrations.hollihop.error_reporting import (
    safe_sync_error_details,
    safe_sync_error_from_exception,
)


class HollihopSyncErrorReportingV68Tests(unittest.TestCase):
    def test_known_error_categorized(self):
        data = safe_sync_error_details({"error": "IntegrityError"})
        self.assertEqual(data["error"], "IntegrityError")
        self.assertIn("constraint", data["reason"])

    def test_legacy_secret_never_exposed(self):
        data = safe_sync_error_details({"error": "HollihopError: Bearer very_secret password=abc"})
        self.assertEqual(data["error"], "HollihopError")
        self.assertNotIn("very_secret", str(data))
        self.assertNotIn("abc", str(data))

    def test_raw_api_errors_not_serialized(self):
        exc = ValueError("User +998901234567 access_key=ABC_secret")
        data = safe_sync_error_from_exception(exc)
        self.assertNotIn("+998", str(data))
        self.assertNotIn("ABC_secret", str(data))

    def test_http_status_safe(self):
        class ApiError(Exception):
            code = 429
        data = safe_sync_error_from_exception(ApiError("token=secret"))
        self.assertEqual(data["http_status"], 429)
        self.assertIn("rate limit", data["reason"])

    def test_unknown_error_not_reflected(self):
        data = safe_sync_error_details({"error": "UnexpectedException: /home/private/path password=abc"})
        self.assertEqual(data["error"], "UnexpectedException")
        self.assertNotIn("/home", str(data))

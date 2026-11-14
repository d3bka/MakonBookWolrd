"""V69: a client must not choose its own IP for rate limits or audit fields."""
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.base.client_ip import client_ip
from apps.sat import event_registration, guest_views, views as sat_views
from apps.sat.public_placement_views import _public_placement_rate_allowed


class ClientIpTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_forwarded_for_is_ignored(self):
        request = self.rf.get("/", HTTP_X_FORWARDED_FOR="6.6.6.6", REMOTE_ADDR="10.0.0.5")
        self.assertEqual(client_ip(request), "10.0.0.5")

    def test_nginx_real_ip_wins(self):
        request = self.rf.get("/", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.9",
                              HTTP_X_REAL_IP="203.0.113.9", REMOTE_ADDR="172.18.0.4")
        self.assertEqual(client_ip(request), "203.0.113.9")

    def test_every_legacy_helper_uses_the_trusted_ip(self):
        request = self.rf.get("/", HTTP_X_FORWARDED_FOR="6.6.6.6", HTTP_X_REAL_IP="203.0.113.9")
        self.assertEqual(guest_views.get_client_ip(request), "203.0.113.9")
        self.assertEqual(sat_views.get_client_ip(request), "203.0.113.9")
        self.assertEqual(event_registration.client_ip(request), "203.0.113.9")


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "xff-v69"}})
class PlacementRateLimitSpoofTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.rf = RequestFactory()

    def test_rotating_forwarded_for_does_not_reset_the_ip_limit(self):
        results = []
        for n in range(13):
            request = self.rf.post("/", HTTP_X_FORWARDED_FOR=f"198.51.100.{n}", HTTP_X_REAL_IP="203.0.113.9")
            allowed, _ = _public_placement_rate_allowed(request, phone=f"+99890000{n:04d}")
            results.append(allowed)
        self.assertTrue(all(results[:12]))
        self.assertFalse(results[12])

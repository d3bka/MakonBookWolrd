"""V85: public redesign — holiday calendar, previews and the new public pages."""
from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.base.models import HolidayTheme
from apps.base.seasons import HOLIDAY_GREETINGS, holiday_for_date


class HolidayCalendarTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_seeded_calendar_covers_moving_holidays(self):
        # Seeded by migration 0048: Ramazon/Qurbon Hayit move every year.
        self.assertEqual(holiday_for_date(date(2026, 3, 21))["key"], "ramazon-hayit")
        self.assertEqual(holiday_for_date(date(2026, 5, 27))["key"], "qurbon-hayit")
        self.assertEqual(holiday_for_date(date(2027, 3, 11))["key"], "ramazon-hayit")
        self.assertEqual(holiday_for_date(date(2027, 3, 8))["key"], "womens-day")
        self.assertEqual(holiday_for_date(date(2026, 10, 1))["key"], "teachers-day")
        self.assertEqual(holiday_for_date(date(2026, 12, 8))["key"], "constitution")
        self.assertEqual(holiday_for_date(date(2026, 12, 31))["key"], "new-year")
        self.assertIsNone(holiday_for_date(date(2026, 11, 17)))

    def test_shortest_window_wins_when_holidays_overlap(self):
        # 2026-03-21 is inside Navruz (14–28 March) and Ramazon Hayit (19–22 March).
        holiday = holiday_for_date(date(2026, 3, 21))
        self.assertEqual(holiday["key"], "ramazon-hayit")
        self.assertEqual(holiday_for_date(date(2026, 3, 25))["key"], "navruz")

    def test_manager_edit_takes_effect_at_once(self):
        day = date(2026, 11, 17)
        self.assertIsNone(holiday_for_date(day))
        row = HolidayTheme.objects.create(key="independence", start_date=day, end_date=day)
        self.assertEqual(holiday_for_date(day)["key"], "independence")
        row.is_active = False
        row.save()
        self.assertIsNone(holiday_for_date(day))

    def test_empty_calendar_falls_back_to_built_in_dates(self):
        HolidayTheme.objects.all().delete()
        cache.clear()
        self.assertEqual(holiday_for_date(date(2027, 3, 21))["key"], "navruz")

    def test_dates_are_validated(self):
        with self.assertRaises(ValidationError):
            HolidayTheme(key="navruz", start_date=date(2027, 3, 28), end_date=date(2027, 3, 14)).full_clean()
        with self.assertRaises(ValidationError):
            HolidayTheme(key="navruz", start_date=date(2027, 1, 1), end_date=date(2027, 5, 1)).full_clean()

    def test_every_holiday_has_three_greetings(self):
        for key, _label in HolidayTheme.KEY_CHOICES:
            with self.subTest(key=key):
                self.assertEqual(set(HOLIDAY_GREETINGS[key]), {"en", "ru", "uz"})
                self.assertTrue(all(HOLIDAY_GREETINGS[key].values()))


class FestivePreviewTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(DEBUG=False)
    def test_visitors_cannot_switch_the_decor(self):
        response = self.client.get("/?festive=navruz")
        self.assertNotContains(response, 'data-festive="navruz"')

    @override_settings(DEBUG=False)
    def test_staff_can_preview_any_holiday_or_season(self):
        staff = User.objects.create_user("decor", password="pw-123456", is_staff=True)
        self.client.force_login(staff)
        # Signed-in users are sent from "/" to their workspace: preview on a public page.
        url = reverse("public_placement_list")
        response = self.client.get(url + "?festive=navruz")
        self.assertContains(response, 'data-festive="navruz"')
        self.assertContains(response, HOLIDAY_GREETINGS["navruz"]["ru"])
        response = self.client.get(url + "?festive=winter")
        self.assertContains(response, 'data-season="winter"')
        self.assertNotContains(response, "data-festive=\"navruz\"")


class PublicPagesTests(TestCase):
    def test_landing_has_every_block_and_the_sign_up(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        for anchor in ('id="platform"', 'id="courses"', 'id="results"', 'id="parents"', 'id="mock-exams"', 'id="faq"'):
            self.assertContains(response, anchor, count=1)
        self.assertContains(response, reverse("register"))
        self.assertContains(response, reverse("public_placement_list"))
        self.assertContains(response, "Check your level")
        self.assertContains(response, "makon-public-v85.js")

    def test_signed_in_student_skips_the_landing(self):
        user = User.objects.create_user("v85student", password="pw-123456")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_auth_pages_use_the_new_shell(self):
        for name in ("login", "register", "forgot_password", "password_reset_confirm"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="mbp-header"')
                self.assertContains(response, "makon-public-v85.css")
                self.assertContains(response, "data-submit-once")

    def test_login_keeps_google_forgot_and_sign_up(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, reverse("forgot_password"))
        self.assertContains(response, reverse("register"))
        self.assertContains(response, "/accounts/google/login/")

    def test_parent_portal_and_level_check_share_the_header(self):
        for url in (reverse("rating_parent_lookup"), reverse("public_placement_list")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="mbp-header"', count=1)
        parent = self.client.get(reverse("rating_parent_lookup"))
        self.assertContains(parent, "data-mb642-parent-locale")
        self.assertContains(parent, 'class="mbp-footer"')

    def test_every_translation_key_in_templates_exists(self):
        root = Path(settings.BASE_DIR)
        js = (root / "static/assets/js/makon-public-v85.js").read_text(encoding="utf-8")
        import re

        keys = set()
        for path in ("templates/public/_header.html", "templates/public/_footer.html", "templates/public/base.html",
                     "templates/landing/home.html", "templates/base/login.html", "templates/base/register.html",
                     "templates/base/register_verify.html", "templates/base/forgot_password.html",
                     "templates/base/password_reset_confirm.html"):
            text = (root / path).read_text(encoding="utf-8")
            keys |= set(re.findall(r'data-i18n(?:-placeholder|-aria)?="([a-z0-9_.]+)"', text))
        missing = sorted(key for key in keys if f"'{key}':" not in js)
        self.assertEqual(missing, [])

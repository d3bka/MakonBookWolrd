"""V70 seasonal themes: calendar, pinning, permissions and shell wiring."""
from datetime import date
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.base.models import SeasonalTheme
from apps.base.seasons import current_season, holiday_for_date, season_for_date, set_season_mode


class SeasonCalendarTests(SimpleTestCase):
    def test_months_map_to_uzbek_seasons(self):
        expected = {1: "winter", 2: "winter", 3: "spring", 5: "spring", 6: "summer", 8: "summer",
                    9: "autumn", 11: "autumn", 12: "winter"}
        for month, season in expected.items():
            with self.subTest(month=month):
                self.assertEqual(season_for_date(date(2026, month, 15)), season)

    def test_holidays(self):
        self.assertEqual(holiday_for_date(date(2027, 3, 21))["key"], "navruz")
        self.assertEqual(holiday_for_date(date(2026, 12, 31))["key"], "new-year")
        self.assertEqual(holiday_for_date(date(2027, 1, 2))["key"], "new-year")
        self.assertEqual(holiday_for_date(date(2026, 9, 1))["key"], "independence")
        self.assertIsNone(holiday_for_date(date(2026, 11, 14)))


class SeasonStateTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_auto_follows_calendar_until_pinned(self):
        self.assertEqual(current_season(date(2027, 4, 1)).key, "spring")
        self.assertTrue(current_season(date(2027, 4, 1)).is_auto)
        set_season_mode("winter")
        state = current_season(date(2027, 4, 1))
        self.assertEqual((state.key, state.mode), ("winter", "winter"))
        set_season_mode("auto")
        self.assertEqual(current_season(date(2027, 7, 1)).key, "summer")

    def test_pinning_invalidates_the_cache(self):
        current_season()  # warm the cache with "auto"
        set_season_mode("spring")
        self.assertEqual(current_season(date(2026, 11, 14)).key, "spring")

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            set_season_mode("monsoon")

    def test_missing_table_never_breaks_pages(self):
        with mock.patch("apps.base.seasons._stored_mode", side_effect=RuntimeError("no table")):
            self.assertEqual(current_season(date(2026, 1, 10)).key, "winter")


class SeasonalThemePageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("manager_seasonal_theme")
        self.manager = User.objects.create_user("season_manager", password="x", first_name="M", last_name="One")
        self.manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.admin = User.objects.create_user("season_admin", password="x", first_name="A", last_name="One")
        self.admin.groups.add(Group.objects.get_or_create(name="Admin")[0])
        self.teacher = User.objects.create_user("season_teacher", password="x", first_name="T", last_name="One")
        self.teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.student = User.objects.create_user("season_student", password="x", first_name="S", last_name="One")

    def test_only_admin_and_manager_can_open_or_change(self):
        for user in (self.teacher, self.student):
            self.client.force_login(user)
            with self.subTest(user=user.username):
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.post(self.url, {"mode": "summer"}).status_code, 403)
        self.assertFalse(SeasonalTheme.objects.exists())
        for user in (self.manager, self.admin):
            self.client.force_login(user)
            with self.subTest(user=user.username):
                self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_manager_pins_a_season_for_everyone(self):
        self.client.force_login(self.manager)
        response = self.client.post(self.url, {"mode": "spring"})
        self.assertRedirects(response, self.url)
        row = SeasonalTheme.objects.get(pk=1)
        self.assertEqual((row.mode, row.updated_by), ("spring", self.manager))
        self.client.force_login(self.student)
        page = self.client.get(reverse("settings_page"))
        self.assertContains(page, 'data-season="spring"')
        self.assertContains(page, 'data-season-layer="spring"')
        self.assertContains(page, "data-season-fx-toggle")

    def test_bad_mode_does_not_change_anything(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {"mode": "monsoon"})
        self.assertFalse(SeasonalTheme.objects.exclude(mode="auto").exists())

    def test_page_shows_every_season_preview(self):
        self.client.force_login(self.admin)
        page = self.client.get(self.url)
        for key in ("winter", "spring", "summer", "autumn"):
            self.assertContains(page, f'data-season-card="{key}"')
        # automatic is the default, so it shows as active and every season offers a pin button
        self.assertContains(page, 'name="mode" value="spring"')
        self.assertNotContains(page, 'value="auto"')

    def test_staff_shell_has_layer_nav_and_assets(self):
        self.client.force_login(self.manager)
        page = self.client.get(reverse("manager_dashboard_root"))
        self.assertContains(page, "data-season-layer=")
        self.assertContains(page, "assets/css/season-v70.css")
        self.assertContains(page, "assets/js/season-v70.js")
        self.assertContains(page, 'data-nav-key="seasonal-theme"')

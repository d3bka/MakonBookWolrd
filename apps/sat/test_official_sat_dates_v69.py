"""V69: SAT dates are admin-managed, can be provisional, and never block a goal."""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.checks import run_checks
from django.test import TestCase
from django.utils import timezone

from apps.sat.models import DreamUniversity, OfficialSatDate, StudentGoalProfile
from apps.sat.student_goal_forms import StudentGoalProfileForm


class OfficialSatDateFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("dates-student", password="x")
        self.university = DreamUniversity.objects.create(name="Dates University", country="United States")
        OfficialSatDate.objects.all().delete()
        self.today = timezone.localdate()

    def _form(self, exam_date=None):
        data = {
            "university_choice": f"university:{self.university.pk}",
            "target_sat_score": 1450,
            "daily_study_minutes_goal": 45,
            "weekly_study_days_goal": 5,
        }
        if exam_date:
            data["exam_date"] = exam_date.isoformat()
        return StudentGoalProfileForm(data=data, instance=StudentGoalProfile(user=self.user))

    def test_migration_seeds_confirmed_and_provisional_dates(self):
        # setUp wiped the table; re-run the seed function from the migration.
        from importlib import import_module
        from django.apps import apps as global_apps
        seed = import_module("apps.sat.migrations.0067_official_sat_dates").seed_dates
        seed(global_apps, None)
        self.assertTrue(OfficialSatDate.objects.filter(date=date(2027, 6, 5), is_confirmed=True).exists())
        self.assertTrue(OfficialSatDate.objects.filter(date=date(2028, 6, 3), is_confirmed=False).exists())

    def test_choices_come_from_admin_and_mark_provisional(self):
        soon = self.today + timedelta(days=30)
        later = self.today + timedelta(days=90)
        OfficialSatDate.objects.create(date=soon)
        OfficialSatDate.objects.create(date=later, is_confirmed=False)
        OfficialSatDate.objects.create(date=self.today + timedelta(days=60), is_active=False)
        labels = dict(self._form().fields["exam_date"].choices)
        self.assertIn(soon.isoformat(), labels)
        self.assertIn("(provisional)", labels[later.isoformat()])
        self.assertEqual(len(labels), 3)  # placeholder + two active dates

    def test_admin_added_date_is_accepted(self):
        exam = self.today + timedelta(days=45)
        OfficialSatDate.objects.create(date=exam)
        form = self._form(exam)
        self.assertTrue(form.is_valid(), form.errors)

    def test_date_not_in_admin_list_is_rejected(self):
        OfficialSatDate.objects.create(date=self.today + timedelta(days=45))
        form = self._form(self.today + timedelta(days=46))
        self.assertFalse(form.is_valid())
        self.assertIn("exam_date", form.errors)

    def test_no_upcoming_dates_never_blocks_saving_a_goal(self):
        OfficialSatDate.objects.create(date=self.today - timedelta(days=10))
        form = self._form()
        self.assertTrue(form.no_upcoming_official_dates)
        self.assertTrue(form.is_valid(), form.errors)


class OfficialSatDateCheckTests(TestCase):
    databases = {"default"}

    def test_warns_when_fewer_than_two_confirmed_upcoming_dates(self):
        OfficialSatDate.objects.all().delete()
        OfficialSatDate.objects.create(date=timezone.localdate() + timedelta(days=20))
        ids = [m.id for m in run_checks(databases=["default"])]
        self.assertIn("sat.W001", ids)

    def test_quiet_when_dates_are_configured(self):
        OfficialSatDate.objects.all().delete()
        for days in (20, 60):
            OfficialSatDate.objects.create(date=timezone.localdate() + timedelta(days=days))
        ids = [m.id for m in run_checks(databases=["default"])]
        self.assertNotIn("sat.W001", ids)

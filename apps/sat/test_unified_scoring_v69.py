"""V69: practice/homework and event/placement attempts share one SAT scoring engine."""
import uuid
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from apps.sat.guest_views import get_event_question_totals, regular_score_from_counts
from apps.sat.models import English_Question, Math_Question, Test, TestReview
from apps.sat.views import _module_totals_for_run, _score_from_counts


def counts(e1, e2, m1, m2):
    return {"english": {"m1": e1, "m2": e2}, "math": {"m1": m1, "m2": m2}}


class UnifiedScoringTests(TestCase):
    def make(self, model, test, module, count):
        model.objects.bulk_create([
            model(test=test, module=module, number=i + 1, answer="A") for i in range(count)
        ])

    def standard_test(self):
        test = Test.objects.create(name="Standard 27/22")
        for module in ("module_1", "module_2"):
            self.make(English_Question, test, module, 27)
            self.make(Math_Question, test, module, 22)
        return test

    def test_standard_tests_score_exactly_as_before(self):
        test = self.standard_test()
        full = [("english", "m1"), ("english", "m2"), ("math", "m1"), ("math", "m2")]
        totals = _module_totals_for_run(test, full)
        for sample in (counts(27, 27, 22, 22), counts(20, 14, 15, 9), counts(0, 0, 0, 0), counts(9, 3, 4, 1)):
            with self.subTest(sample=sample):
                self.assertEqual(_score_from_counts("full", sample, totals), _score_from_counts("full", sample))

    def test_registered_and_event_paths_agree_on_non_standard_tests(self):
        test = Test.objects.create(name="Short 10/10")
        for module in ("module_1", "module_2"):
            self.make(English_Question, test, module, 10)
            self.make(Math_Question, test, module, 10)
        full = [("english", "m1"), ("english", "m2"), ("math", "m1"), ("math", "m2")]
        sample = counts(10, 10, 10, 10)
        registered = _score_from_counts("full", sample, _module_totals_for_run(test, full))
        event = regular_score_from_counts("full", sample, get_event_question_totals(test))
        self.assertEqual(registered, event)
        self.assertEqual(registered["total"], 1600)  # raw counts used to give far less

    def test_single_module_run_is_not_scored_as_zero_on_the_missing_module(self):
        test = self.standard_test()
        run = [("english", "m1")]
        result = _score_from_counts("ebrw_only", counts(27, 0, 0, 0), _module_totals_for_run(test, run))
        self.assertEqual(result["total"], 800)
        legacy = _score_from_counts("ebrw_only", counts(27, 0, 0, 0))
        self.assertLess(legacy["total"], 800)  # the old bug this fixes

    def test_module_totals_ignore_modules_outside_the_run(self):
        test = self.standard_test()
        totals = _module_totals_for_run(test, [("math", "m2")])
        self.assertEqual(totals, {"english": {"m1": 0, "m2": 0}, "math": {"m1": 0, "m2": 22}})


class RescoreCommandTests(TestCase):
    def test_dry_run_reports_and_apply_skips_unscorable_reviews(self):
        user = User.objects.create_user("rescore-student", password="x")
        test = Test.objects.create(name="Rescore test")
        review = TestReview.objects.create(user=user, test=test, attempt_id=uuid.uuid4(), score=1234, key="r" * 100)
        out = StringIO()
        call_command("rescore_sat_reviews", stdout=out)
        self.assertIn("Dry run", out.getvalue())
        call_command("rescore_sat_reviews", "--apply", stdout=StringIO())
        review.refresh_from_db()
        self.assertEqual(review.score, 1234)  # no modules to recompute from: left untouched

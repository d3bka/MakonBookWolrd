"""Re-score stored SAT reviews with the unified scoring engine (dry run by default).

V69 made practice/homework scoring use the same normalised engine as
events/placement. Standard 27/27/22/22 tests score exactly as before; tests with
non-standard module sizes and single-module runs change. Results pages no
longer rewrite stored scores, so apply the new engine to history explicitly:

    python manage.py rescore_sat_reviews                 # report only
    python manage.py rescore_sat_reviews --apply         # write changed scores
    python manage.py rescore_sat_reviews --test "DAY 12" # one test
"""
from django.core.management.base import BaseCommand

from apps.sat.models import TestReview


class Command(BaseCommand):
    help = "Recompute stored SAT review scores with the unified engine (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the recomputed scores.")
        parser.add_argument("--test", default="", help="Only reviews of this test name.")
        parser.add_argument("--limit", type=int, default=0, help="Stop after this many reviews (0 = all).")

    def handle(self, *args, apply=False, test="", limit=0, **options):
        from apps.sat.views import _calculate_attempt_score

        reviews = (
            TestReview.objects.filter(test__isnull=False, score__isnull=False, user__isnull=False)
            .select_related("test", "user", "classroom")
            .order_by("pk")
        )
        if test:
            reviews = reviews.filter(test__name=test)

        checked = changed = unscorable = 0
        for review in reviews.iterator():
            if limit and checked >= limit:
                break
            checked += 1
            result = _calculate_attempt_score(
                review.user, review.test, review.attempt_id, classroom=review.classroom
            )
            if not result:
                unscorable += 1
                continue
            new_score = result.get("total", 0) if isinstance(result, dict) else 0
            if new_score == review.score:
                continue
            changed += 1
            self.stdout.write(
                f"review #{review.pk} {review.user.username} · {review.test.name}: {review.score} -> {new_score}"
            )
            if apply:
                # drop the cached PDF too, so the certificate is rebuilt with the new score
                TestReview.objects.filter(pk=review.pk).update(score=new_score, certificate='')

        verb = "Updated" if apply else "Would update"
        self.stdout.write(self.style.SUCCESS(
            f"Checked {checked} review(s): {verb.lower()} {changed}, {unscorable} could not be re-scored "
            "(missing modules) and were left unchanged." + ("" if apply else " Dry run — re-run with --apply.")
        ))

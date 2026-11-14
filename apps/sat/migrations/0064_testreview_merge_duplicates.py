"""Merge duplicate TestReview rows per attempt (unique constraints follow in 0065).

Concurrent results/backfill requests could insert two reviews for the same
(user, test, attempt_id, classroom). This migration keeps the best row of each
group, folds useful data from the duplicates into it, repoints homework
submissions and deletes the duplicates.

Keeper choice per group: a scored row first, then one with a share key, then the
earliest created. Irreversible by design (reverse is a no-op): the deleted
duplicates carried no data the keeper does not now hold. A duplicate's own
share key (?review_key=...) stops resolving; the keeper's key keeps working.
"""
from django.db import migrations
from django.db.models import Count

GROUP_FIELDS = (
    ("test_id", ("user_id", "test_id", "attempt_id", "classroom_id")),
    ("makeup_test_id", ("user_id", "makeup_test_id", "attempt_id", "classroom_id")),
)


def _keeper_sort_key(review):
    return (
        review.score is None,          # scored rows first
        not review.key,                # rows with a share key next
        review.created_at,             # then the original row
        review.pk,
    )


def merge_duplicate_reviews(apps, schema_editor):
    TestReview = apps.get_model("sat", "TestReview")
    Submission = apps.get_model("sat", "ClassroomHomeworkSubmission")
    merged = 0
    for target_field, fields in GROUP_FIELDS:
        groups = (
            TestReview.objects.filter(**{f"{target_field}__isnull": False, "user_id__isnull": False})
            .values(*fields)
            .annotate(rows=Count("id"))
            .filter(rows__gt=1)
        )
        for group in groups.iterator():
            lookup = {field: group[field] for field in fields}
            rows = sorted(TestReview.objects.filter(**lookup), key=_keeper_sort_key)
            keeper, duplicates = rows[0], rows[1:]
            changed = set()
            for dup in duplicates:
                if not keeper.certificate and dup.certificate:
                    keeper.certificate = dup.certificate
                    changed.add("certificate")
                if dup.attempt_started_at and (
                    keeper.attempt_started_at is None or dup.attempt_started_at < keeper.attempt_started_at
                ):
                    keeper.attempt_started_at = dup.attempt_started_at
                    changed.add("attempt_started_at")
                if dup.integrity_violation_count > keeper.integrity_violation_count:
                    keeper.integrity_violation_count = dup.integrity_violation_count
                    changed.add("integrity_violation_count")
                if dup.integrity_terminated and not keeper.integrity_terminated:
                    keeper.integrity_terminated = True
                    changed.add("integrity_terminated")
                if dup.domains and not keeper.domains:
                    keeper.domains = True
                    changed.add("domains")
            if changed:
                keeper.save(update_fields=sorted(changed))
            dup_ids = [dup.pk for dup in duplicates]
            Submission.objects.filter(test_review_id__in=dup_ids).update(test_review_id=keeper.pk)
            TestReview.objects.filter(pk__in=dup_ids).delete()
            merged += len(dup_ids)
    if merged:
        print(f"\n  Merged {merged} duplicate TestReview row(s).")


class Migration(migrations.Migration):

    dependencies = [
        ("sat", "0063_global_event_attempt_run_mode"),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_reviews, migrations.RunPython.noop),
    ]

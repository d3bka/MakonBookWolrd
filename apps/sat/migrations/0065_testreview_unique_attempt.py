"""Enforce one TestReview per attempt and classroom scope (after 0064 merged duplicates).

Kept separate from the data merge so PostgreSQL never alters the table in the
same transaction that deleted rows with deferred FK triggers pending.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sat", "0064_testreview_merge_duplicates"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="testreview",
            constraint=models.UniqueConstraint(
                condition=models.Q(("classroom__isnull", False), ("test__isnull", False)),
                fields=("user", "test", "attempt_id", "classroom"),
                name="sat_tr_unique_attempt_classroom",
            ),
        ),
        migrations.AddConstraint(
            model_name="testreview",
            constraint=models.UniqueConstraint(
                condition=models.Q(("classroom__isnull", True), ("test__isnull", False)),
                fields=("user", "test", "attempt_id"),
                name="sat_tr_unique_attempt_solo",
            ),
        ),
        migrations.AddConstraint(
            model_name="testreview",
            constraint=models.UniqueConstraint(
                condition=models.Q(("classroom__isnull", False), ("makeup_test__isnull", False)),
                fields=("user", "makeup_test", "attempt_id", "classroom"),
                name="sat_tr_unique_makeup_attempt_classroom",
            ),
        ),
        migrations.AddConstraint(
            model_name="testreview",
            constraint=models.UniqueConstraint(
                condition=models.Q(("classroom__isnull", True), ("makeup_test__isnull", False)),
                fields=("user", "makeup_test", "attempt_id"),
                name="sat_tr_unique_makeup_attempt_solo",
            ),
        ),
    ]

# Generated for MakonBook World V50.3 MVP.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="WorldRating",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject", models.CharField(choices=[("math", "Math"), ("rw", "Reading & Writing")], max_length=8)),
                ("rating", models.PositiveIntegerField(db_index=True, default=1000)),
                ("wins", models.PositiveIntegerField(default=0)),
                ("losses", models.PositiveIntegerField(default=0)),
                ("draws", models.PositiveIntegerField(default=0)),
                ("streak", models.IntegerField(default=0)),
                ("ranked_played", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="world_ratings", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-rating", "user_id"]},
        ),
        migrations.CreateModel(
            name="WorldMatch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("subject", models.CharField(choices=[("math", "Math"), ("rw", "Reading & Writing")], max_length=8)),
                ("mode", models.CharField(choices=[("quick", "Quick Match"), ("ranked", "Ranked")], max_length=8)),
                ("status", models.CharField(choices=[("waiting", "Waiting"), ("active", "Active"), ("completed", "Completed"), ("cancelled", "Cancelled")], db_index=True, default="waiting", max_length=12)),
                ("question_ids", models.JSONField(blank=True, default=list)),
                ("player1_score", models.PositiveSmallIntegerField(default=0)),
                ("player2_score", models.PositiveSmallIntegerField(default=0)),
                ("player1_rating_before", models.PositiveIntegerField(default=1000)),
                ("player2_rating_before", models.PositiveIntegerField(default=1000)),
                ("player1_rating_after", models.PositiveIntegerField(default=1000)),
                ("player2_rating_after", models.PositiveIntegerField(default=1000)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("player1", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="world_matches_as_player1", to=settings.AUTH_USER_MODEL)),
                ("player2", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="world_matches_as_player2", to=settings.AUTH_USER_MODEL)),
                ("winner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="world_matches_won", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="WorldAnswer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question_index", models.PositiveSmallIntegerField()),
                ("selected_answer", models.CharField(blank=True, max_length=400)),
                ("is_correct", models.BooleanField(default=False)),
                ("answered_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("match", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="answers", to="world.worldmatch")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="world_answers", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["question_index"]},
        ),
        migrations.AddConstraint(model_name="worldrating", constraint=models.UniqueConstraint(fields=("user", "subject"), name="world_unique_user_subject_rating")),
        migrations.AddIndex(model_name="worldrating", index=models.Index(fields=["subject", "-rating"], name="world_subject_rating_idx")),
        migrations.AddIndex(model_name="worldmatch", index=models.Index(fields=["status", "subject", "mode", "created_at"], name="world_queue_lookup_idx")),
        migrations.AddConstraint(model_name="worldanswer", constraint=models.UniqueConstraint(fields=("match", "user", "question_index"), name="world_unique_match_user_question")),
    ]

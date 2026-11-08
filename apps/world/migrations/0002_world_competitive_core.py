from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import secrets
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("world", "0001_initial"),
        ("sat", "0049_lesson_vocabulary_quiz_resource_v50211"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GameQuestionPool",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject", models.CharField(choices=[("math", "Math"), ("rw", "Reading & Writing")], db_index=True, max_length=8)),
                ("difficulty", models.CharField(choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")], db_index=True, default="medium", max_length=10)),
                ("game_enabled", models.BooleanField(db_index=True, default=True)),
                ("quality_verified", models.BooleanField(db_index=True, default=False)),
                ("estimated_seconds", models.PositiveSmallIntegerField(default=60)),
                ("times_used", models.PositiveIntegerField(default=0)),
                ("answer_count", models.PositiveIntegerField(default=0)),
                ("correct_count", models.PositiveIntegerField(default=0)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("english_question", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="world_pool_entry", to="sat.english_question")),
                ("math_question", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="world_pool_entry", to="sat.math_question")),
            ],
        ),
        migrations.AddField(
            model_name="worldmatch",
            name="disconnect_forfeit_user",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="world_disconnect_forfeits", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(model_name="worldmatch", name="mmr_weight", field=models.DecimalField(decimal_places=2, default=1.0, max_digits=4)),
        migrations.AddField(model_name="worldmatch", name="player1_last_seen_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="worldmatch", name="player2_last_seen_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="worldmatch", name="question_pool_ids", field=models.JSONField(blank=True, default=list)),
        migrations.AlterField(model_name="worldmatch", name="player1_score", field=models.PositiveIntegerField(default=0)),
        migrations.AlterField(model_name="worldmatch", name="player2_score", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="worldanswer", name="integrity_flag", field=models.CharField(choices=[("ok", "OK"), ("too_fast", "Suspiciously fast"), ("timeout", "Timed out")], default="ok", max_length=16)),
        migrations.AddField(model_name="worldanswer", name="points", field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="worldanswer", name="pool_entry", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="answers", to="world.gamequestionpool")),
        migrations.AddField(model_name="worldanswer", name="response_ms", field=models.PositiveIntegerField(default=0)),
        migrations.CreateModel(
            name="WorldQuestionTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question_index", models.PositiveSmallIntegerField()),
                ("token", models.CharField(db_index=True, default=secrets.token_urlsafe, editable=False, max_length=64, unique=True)),
                ("issued_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("deadline_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("match", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="question_tickets", to="world.worldmatch")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="world_question_tickets", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["question_index"]},
        ),
        migrations.AddIndex(model_name="gamequestionpool", index=models.Index(fields=["subject", "game_enabled", "quality_verified", "difficulty"], name="world_pool_pick_idx")),
        migrations.AddConstraint(
            model_name="gamequestionpool",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("english_question__isnull", True), ("math_question__isnull", False), ("subject", "math"))
                    | models.Q(("english_question__isnull", False), ("math_question__isnull", True), ("subject", "rw"))
                ),
                name="world_pool_source_matches_subject",
            ),
        ),
        migrations.AddConstraint(model_name="worldquestionticket", constraint=models.UniqueConstraint(fields=("match", "user", "question_index"), name="world_unique_question_ticket")),
    ]

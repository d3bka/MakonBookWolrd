from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import secrets


class Migration(migrations.Migration):
    dependencies = [
        ("world", "0004_world_multiplayer_foundation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="worldmultiplayerroom",
            name="current_question_index",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="worldmultiplayerroom",
            name="question_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="WorldMultiplayerQuestionTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question_index", models.PositiveSmallIntegerField()),
                ("token", models.CharField(db_index=True, default=secrets.token_urlsafe, editable=False, max_length=64, unique=True)),
                ("issued_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("deadline_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="question_tickets", to="world.worldmultiplayerroom")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="world_multiplayer_question_tickets", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["question_index"]},
        ),
        migrations.CreateModel(
            name="WorldMultiplayerAnswer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question_index", models.PositiveSmallIntegerField()),
                ("selected_answer", models.CharField(blank=True, max_length=400)),
                ("is_correct", models.BooleanField(default=False)),
                ("points", models.PositiveSmallIntegerField(default=0)),
                ("response_ms", models.PositiveIntegerField(default=0)),
                ("integrity_flag", models.CharField(choices=[("ok", "OK"), ("too_fast", "Suspiciously fast"), ("timeout", "Timed out")], default="ok", max_length=16)),
                ("answered_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("pool_entry", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="multiplayer_answers", to="world.gamequestionpool")),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="answers", to="world.worldmultiplayerroom")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="world_multiplayer_answers", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["question_index", "answered_at"]},
        ),
        migrations.AddConstraint(
            model_name="worldmultiplayerquestionticket",
            constraint=models.UniqueConstraint(fields=("room", "user", "question_index"), name="world_mp_unique_question_ticket"),
        ),
        migrations.AddConstraint(
            model_name="worldmultiplayeranswer",
            constraint=models.UniqueConstraint(fields=("room", "user", "question_index"), name="world_mp_unique_room_user_question"),
        ),
    ]

# Generated for MakonBook V50.4.1
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("world", "0003_world_rematch_invites"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorldMultiplayerRoom",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("subject", models.CharField(choices=[("math", "Math"), ("rw", "Reading & Writing")], max_length=8)),
                ("capacity", models.PositiveSmallIntegerField(choices=[(3, "3 players"), (4, "4 players")], default=4)),
                ("join_code", models.CharField(db_index=True, max_length=8, unique=True)),
                ("status", models.CharField(choices=[("lobby", "Lobby"), ("active", "Active"), ("completed", "Completed"), ("cancelled", "Cancelled")], db_index=True, default="lobby", max_length=12)),
                ("question_pool_ids", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("host", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="world_multiplayer_rooms_hosted", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="WorldMultiplayerSeat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seat_number", models.PositiveSmallIntegerField()),
                ("is_ready", models.BooleanField(db_index=True, default=False)),
                ("score", models.PositiveIntegerField(default=0)),
                ("joined_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="seats", to="world.worldmultiplayerroom")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="world_multiplayer_seats", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["seat_number"]},
        ),
        migrations.AddIndex(
            model_name="worldmultiplayerroom",
            index=models.Index(fields=["status", "subject", "created_at"], name="world_mp_room_lookup_idx"),
        ),
        migrations.AddConstraint(
            model_name="worldmultiplayerseat",
            constraint=models.UniqueConstraint(fields=("room", "user"), name="world_mp_unique_room_user"),
        ),
        migrations.AddConstraint(
            model_name="worldmultiplayerseat",
            constraint=models.UniqueConstraint(fields=("room", "seat_number"), name="world_mp_unique_room_seat"),
        ),
        migrations.AddConstraint(
            model_name="worldmultiplayerseat",
            constraint=models.CheckConstraint(condition=models.Q(("seat_number__gte", 1), ("seat_number__lte", 4)), name="world_mp_seat_range_1_4"),
        ),
    ]

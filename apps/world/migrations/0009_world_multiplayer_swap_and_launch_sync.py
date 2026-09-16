from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("world", "0008_world_multiplayer_core_hardening"),
    ]

    operations = [
        migrations.AddField(
            model_name="worldmultiplayerseat",
            name="arena_ready_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RemoveConstraint(
            model_name="worldmultiplayerseat",
            name="world_mp_unique_room_seat",
        ),
        migrations.AddConstraint(
            model_name="worldmultiplayerseat",
            constraint=models.UniqueConstraint(
                deferrable=models.Deferrable.DEFERRED,
                fields=("room", "seat_number"),
                name="world_mp_unique_room_seat",
            ),
        ),
        migrations.CreateModel(
            name="WorldMultiplayerSeatSwapRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("accepted", "Accepted"),
                            ("declined", "Declined"),
                            ("cancelled", "Cancelled"),
                            ("expired", "Expired"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=12,
                    ),
                ),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                (
                    "requester",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="world_multiplayer_swap_requests_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seat_swap_requests",
                        to="world.worldmultiplayerroom",
                    ),
                ),
                (
                    "target",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="world_multiplayer_swap_requests_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["room", "status", "created_at"], name="world_mp_swap_room_idx"),
                    models.Index(fields=["target", "status", "created_at"], name="world_mp_swap_target_idx"),
                ],
            },
        ),
    ]

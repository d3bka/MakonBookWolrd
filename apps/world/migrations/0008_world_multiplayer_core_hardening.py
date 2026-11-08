from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("world", "0007_world_multiplayer_room_access_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="worldmultiplayerroom",
            name="game_mode",
            field=models.CharField(
                choices=[
                    ("ffa", "Free for all"),
                    ("team_2v2", "2v2"),
                    ("survival", "Survival"),
                    ("classroom", "Classroom Battle"),
                ],
                db_index=True,
                default="ffa",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="worldmultiplayerroom",
            name="state_version",
            field=models.PositiveBigIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="worldmultiplayerseat",
            name="team",
            field=models.CharField(
                blank=True,
                choices=[("", "No team"), ("a", "Team A"), ("b", "Team B")],
                default="",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="worldmultiplayerseat",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name="worldmultiplayerseat",
            name="is_connected",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name="worldmultiplayerseat",
            name="disconnected_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="worldmultiplayerseat",
            name="left_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="worldmultiplayerroom",
            index=models.Index(
                fields=["status", "access_type", "game_mode", "subject", "capacity", "question_count", "created_at"],
                name="world_mp_public_queue_idx",
            ),
        ),
    ]

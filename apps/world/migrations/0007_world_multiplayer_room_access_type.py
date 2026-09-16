from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("world", "0006_world_multiplayer_room_controls"),
    ]

    operations = [
        migrations.AddField(
            model_name="worldmultiplayerroom",
            name="access_type",
            field=models.CharField(choices=[("private", "Private"), ("public", "Public")], db_index=True, default="private", max_length=12),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("world", "0005_world_multiplayer_play_engine"),
    ]

    operations = [
        migrations.AddField(
            model_name="worldmultiplayerroom",
            name="question_count",
            field=models.PositiveSmallIntegerField(
                choices=[(5, "5 questions"), (10, "10 questions"), (15, "15 questions"), (20, "20 questions")],
                default=5,
            ),
        ),
    ]

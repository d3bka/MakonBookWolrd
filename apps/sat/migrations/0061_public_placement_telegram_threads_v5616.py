from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sat", "0060_public_placement_v5610"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicplacementlead",
            name="telegram_threads",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

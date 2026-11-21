from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sat", "0076_sat_attempt_limits_v93"),
    ]

    operations = [
        migrations.AddField(
            model_name="globaleventattempt",
            name="subject_break_until",
            field=models.DateTimeField(blank=True, help_text="End of the break before the next subject", null=True),
        ),
    ]

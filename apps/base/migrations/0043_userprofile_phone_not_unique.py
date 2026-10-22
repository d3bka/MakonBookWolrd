from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0042_referrals_issue_attachments_v524"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="phone_number",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
    ]

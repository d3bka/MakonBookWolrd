from django.db import migrations, models


class Migration(migrations.Migration):
    """V98: imported questions carry an SAT domain, and the AI's suggested fixes wait for a decision."""

    dependencies = [
        ("sat", "0079_import_ai_check_v97"),
    ]

    operations = [
        migrations.AddField(
            model_name="testimportquestion",
            name="domain_name",
            field=models.CharField(blank=True, db_default="", default="", max_length=100, verbose_name="Domain"),
        ),
        migrations.AddField(
            model_name="testimportquestion",
            name="ai_proposal",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="testimportquestion",
            name="ai_proposal_status",
            field=models.CharField(blank=True, db_default="", default="", max_length=12),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    """V97: staging imports keep written-answer / placement fields and the type to publish as."""

    dependencies = [
        ("sat", "0078_placement_diagnostic_v97"),
    ]

    operations = [
        migrations.AddField(
            model_name="testimportjob",
            name="target_test_type",
            field=models.CharField(
                choices=[("regular", "Regular / Practice Test"), ("placement", "Placement Test"), ("event", "Event Test")],
                db_default="regular", default="regular", max_length=20, verbose_name="Publish as",
            ),
        ),
        migrations.AlterField(
            model_name="testimportquestion",
            name="response_type",
            field=models.CharField(
                choices=[
                    ("multiple_choice", "Multiple choice"),
                    ("open_text", "Open text (deterministic matching)"),
                    ("ai_written", "Written answer (checked by AI)"),
                ],
                default="multiple_choice", max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="testimportquestion",
            name="accepted_answers",
            field=models.TextField(blank=True, db_default="", default="", help_text="One accepted answer per line."),
        ),
        migrations.AddField(
            model_name="testimportquestion",
            name="grading_criteria",
            field=models.TextField(blank=True, db_default="", default=""),
        ),
        migrations.AddField(
            model_name="testimportquestion",
            name="placement_tier",
            field=models.CharField(
                blank=True, choices=[("foundation", "Foundation"), ("pre_sat", "Pre-SAT"), ("sat", "SAT")],
                db_default="", default="", max_length=12, verbose_name="Placement tier",
            ),
        ),
        migrations.AddField(
            model_name="testimportquestion",
            name="skill",
            field=models.CharField(blank=True, db_default="", default="", max_length=120),
        ),
        migrations.AddField(
            model_name="testimportquestion",
            name="content_format",
            field=models.CharField(
                choices=[("legacy", "Structured PDF"), ("makon", "MakonBook format")],
                db_default="legacy", default="legacy", max_length=10,
            ),
        ),
    ]

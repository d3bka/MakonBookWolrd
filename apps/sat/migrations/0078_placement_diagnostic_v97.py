from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sat", "0077_event_subject_break_v96"),
    ]

    operations = [
        migrations.AlterField(
            model_name="english_question",
            name="response_type",
            field=models.CharField(
                choices=[
                    ("multiple_choice", "Multiple choice"),
                    ("open_text", "Open text (deterministic matching)"),
                    ("ai_written", "Written answer (checked by AI)"),
                ],
                default="multiple_choice",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="english_question",
            name="placement_tier",
            field=models.CharField(
                blank=True, choices=[("foundation", "Foundation"), ("pre_sat", "Pre-SAT"), ("sat", "SAT")],
                db_default="", default="", max_length=12, verbose_name="Placement tier",
                help_text="Placement tests only: the level this question checks. Tiers decide the recommended course.",
            ),
        ),
        migrations.AddField(
            model_name="english_question",
            name="skill",
            field=models.CharField(
                blank=True, db_default="", default="", max_length=120,
                help_text="Skill shown in the diagnostic result, e.g. Past perfect or Transitions.",
            ),
        ),
        migrations.AddField(
            model_name="english_question",
            name="grading_criteria",
            field=models.TextField(
                blank=True, db_default="", default="",
                help_text="Written answers checked by AI: what a correct answer must do, e.g. 'Requires had + past participle'.",
            ),
        ),
        migrations.AddField(
            model_name="globaleventanswer",
            name="grading",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('sat', '0053_classroomhomeworksubmission_v552'),
    ]

    operations = [
        migrations.AddField(
            model_name='classroomhomeworkassignment',
            name='required_test_mode',
            field=models.CharField(
                choices=[
                    ('full_test', 'Full Test'),
                    ('rw_only', 'Reading & Writing'),
                    ('math_only', 'Math'),
                    ('single_english_m1', 'Reading & Writing · Module 1'),
                    ('single_english_m2', 'Reading & Writing · Module 2'),
                    ('single_math_m1', 'Math · Module 1'),
                    ('single_math_m2', 'Math · Module 2'),
                ],
                default='full_test',
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name='classroomhomeworkassignment',
            name='required_integrity_mode',
            field=models.CharField(
                choices=[
                    ('off', 'Off'),
                    ('standard', 'Standard'),
                    ('strict', 'Strict'),
                ],
                default='off',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='teststage',
            name='attempt_started_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='testreview',
            name='attempt_started_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]

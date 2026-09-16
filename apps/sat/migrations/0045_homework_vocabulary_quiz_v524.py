from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('sat', '0044_classroom_lessons_homework_v524'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classroomhomeworkassignment',
            name='assignment_type',
            field=models.CharField(
                choices=[
                    ('sat_test', 'SAT test'),
                    ('vocabulary_unit', 'Vocabulary practice'),
                    ('vocabulary_quiz', 'Vocabulary quiz'),
                ],
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name='classroomhomeworkassignment',
            name='vocabulary_quiz_mode',
            field=models.CharField(
                choices=[
                    ('word_to_meaning', 'Word to meaning'),
                    ('meaning_to_word', 'Meaning to word'),
                    ('mixed', 'Mixed'),
                ],
                default='mixed',
                max_length=24,
            ),
        ),
    ]

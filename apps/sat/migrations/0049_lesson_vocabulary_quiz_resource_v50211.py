from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('sat', '0048_lesson_test_resources_notifications_v50210'),
    ]

    operations = [
        migrations.AddField(
            model_name='classroomlessonresource',
            name='vocabulary_unit',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='classroom_lesson_resources', to='sat.vocabularyunit'),
        ),
        migrations.AddField(
            model_name='classroomlessonresource',
            name='vocabulary_question_count',
            field=models.PositiveSmallIntegerField(default=10, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)]),
        ),
        migrations.AddField(
            model_name='classroomlessonresource',
            name='vocabulary_quiz_mode',
            field=models.CharField(choices=[('word_to_meaning', 'Word to meaning'), ('meaning_to_word', 'Meaning to word'), ('mixed', 'Mixed')], default='mixed', max_length=32),
        ),
        migrations.AlterField(
            model_name='classroomlessonresource',
            name='resource_type',
            field=models.CharField(choices=[('file', 'File'), ('link', 'Link'), ('presentation', 'Presentation'), ('test', 'SAT Test'), ('vocabulary_quiz', 'Vocabulary Quiz')], default='file', max_length=20),
        ),
    ]

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sat', '0052_testreview_attempt_history_v551'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassroomHomeworkSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('not_started', 'Not started'), ('in_progress', 'In progress'), ('completed', 'Completed'), ('submitted', 'Submitted')], db_index=True, default='not_started', max_length=20)),
                ('source', models.CharField(choices=[('homework', 'Homework'), ('practice_tests', 'Practice Tests'), ('vocabulary', 'Vocabulary')], default='homework', max_length=24)),
                ('attempt_id', models.UUIDField(blank=True, db_index=True, null=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='sat.classroomhomeworkassignment')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='classroom_homework_submissions', to=settings.AUTH_USER_MODEL)),
                ('test_review', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='homework_submissions', to='sat.testreview')),
                ('vocabulary_quiz_attempt', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='homework_submissions', to='sat.vocabularyquizattempt')),
            ],
            options={
                'ordering': ['-updated_at', '-id'],
                'indexes': [
                    models.Index(fields=['student', 'status', '-updated_at'], name='sat_hwsub_student_status'),
                    models.Index(fields=['assignment', 'status'], name='sat_hwsub_assignment_status'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('assignment', 'student'), name='sat_unique_homework_submission_student'),
                ],
            },
        ),
    ]

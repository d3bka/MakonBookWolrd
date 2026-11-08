from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('ratings', '0004_assessment_operations_v61'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='TeacherAssessmentReminder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('pending_count', models.PositiveIntegerField(default=0)),
                ('sent_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessment_reminders', to=settings.AUTH_USER_MODEL)),
            ],
            options={'constraints': [models.UniqueConstraint(fields=('teacher', 'date'), name='rating_unique_teacher_reminder')]},
        ),
    ]

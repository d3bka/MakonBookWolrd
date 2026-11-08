from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('ratings', '0003_termgrade'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.AddField(model_name='ratingassessment', name='lesson_date', field=models.DateField(blank=True, db_index=True, help_text='Lesson date for V61 teacher assessments; legacy history stays NULL.', null=True)),
        migrations.AddConstraint(model_name='ratingassessment', constraint=models.UniqueConstraint(fields=['classroom', 'teacher', 'student', 'lesson_date'], condition=models.Q(lesson_date__isnull=False), name='rating_one_assessment_per_lesson')),
        migrations.CreateModel(name='AssessmentSchedule', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('weekdays', models.JSONField(default=list, help_text='ISO weekdays (Monday=1 to Sunday=7).')),
            ('starts_on', models.DateField(default=django.utils.timezone.localdate)),
            ('ends_on', models.DateField(blank=True, null=True)), ('enabled', models.BooleanField(default=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_assessment_schedules', to=settings.AUTH_USER_MODEL)),
            ('classroom', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessment_schedules', to='sat.classroom')),
            ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessment_schedules', to=settings.AUTH_USER_MODEL)),
        ], options={'constraints': [models.UniqueConstraint(fields=['classroom', 'teacher'], name='rating_schedule_class_teacher')]}),
        migrations.CreateModel(name='AssessmentCalendarException', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('date', models.DateField()),
            ('action', models.CharField(choices=[('cancelled', 'Cancelled / holiday'), ('added', 'Extra lesson')], max_length=12)),
            ('reason', models.CharField(blank=True, max_length=220)), ('created_at', models.DateTimeField(auto_now_add=True)),
            ('changed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exceptions', to='ratings.assessmentschedule')),
        ], options={'constraints': [models.UniqueConstraint(fields=['schedule', 'date'], name='rating_schedule_day_exception')]}),
        migrations.CreateModel(name='AssessmentObligation', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('lesson_date', models.DateField(db_index=True)), ('created_at', models.DateTimeField(auto_now_add=True)),
            ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='obligations', to='ratings.assessmentschedule')),
            ('student', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assessment_obligations', to=settings.AUTH_USER_MODEL)),
        ], options={'constraints': [models.UniqueConstraint(fields=['schedule', 'student', 'lesson_date'], name='rating_obligation_student_day')], 'indexes': [models.Index(fields=['lesson_date', 'schedule'], name='rating_oblig_due_sch')]}),
        migrations.CreateModel(name='AssessmentPenalty', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('amount_uzs', models.PositiveIntegerField(default=5000)),
            ('status', models.CharField(choices=[('open', 'Pending manager review'), ('waived', 'Waived')], default='open', max_length=10)),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('reviewed_at', models.DateTimeField(blank=True, null=True)), ('review_note', models.CharField(blank=True, max_length=500)),
            ('obligation', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='penalty', to='ratings.assessmentobligation')),
            ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='AssessmentDailyReport', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('date', models.DateField(unique=True)),
            ('expected', models.PositiveIntegerField(default=0)),
            ('completed', models.PositiveIntegerField(default=0)),
            ('missed', models.PositiveIntegerField(default=0)),
            ('sent_at', models.DateTimeField(default=django.utils.timezone.now)),
        ]),
        migrations.CreateModel(name='UserActivityDay', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('date', models.DateField(db_index=True)),
            ('first_seen_at', models.DateTimeField(default=django.utils.timezone.now)), ('last_seen_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='makon_activity_days', to=settings.AUTH_USER_MODEL)),
        ], options={'constraints': [models.UniqueConstraint(fields=['user', 'date'], name='rating_unique_user_activity_day')], 'indexes': [models.Index(fields=['date', 'user'], name='rating_activity_date_user')]}),
    ]

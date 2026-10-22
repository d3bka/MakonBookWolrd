import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('sat', '0049_lesson_vocabulary_quiz_resource_v50211'),
    ]

    operations = [
        migrations.AddField(
            model_name='teststage',
            name='integrity_mode',
            field=models.CharField(
                choices=[('off', 'Off'), ('standard', 'Standard'), ('strict', 'Strict')],
                default='standard',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='teststage',
            name='integrity_max_violations',
            field=models.PositiveSmallIntegerField(
                default=3,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(10),
                ],
            ),
        ),
        migrations.AddField(
            model_name='teststage',
            name='integrity_violation_count',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='teststage',
            name='integrity_fullscreen_required',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='teststage',
            name='integrity_monitored_events',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='teststage',
            name='integrity_terminated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='teststage',
            name='integrity_retake_locked',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='teststage',
            name='scheduled_break_started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='teststage',
            name='scheduled_break_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='ClassroomPracticeTestIntegrityPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(
                    choices=[('off', 'Off'), ('standard', 'Standard'), ('strict', 'Strict')],
                    default='standard',
                    max_length=16,
                )),
                ('max_violations', models.PositiveSmallIntegerField(
                    default=3,
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(10),
                    ],
                )),
                ('fullscreen_required', models.BooleanField(default=True)),
                ('monitored_events', models.JSONField(blank=True, default=list)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('classroom', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='practice_test_integrity_policies',
                    to='sat.classroom',
                )),
                ('test', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='classroom_integrity_policies',
                    to='sat.test',
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name='classroompracticetestintegritypolicy',
            constraint=models.UniqueConstraint(
                fields=('classroom', 'test'),
                name='sat_unique_classroom_test_integrity_policy',
            ),
        ),
        migrations.CreateModel(
            name='ExamIntegrityViolation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True)),
                ('event_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('attempt_id', models.UUIDField(db_index=True)),
                ('event_type', models.CharField(
                    choices=[
                        ('tab_hidden', 'Browser tab changed'),
                        ('window_blur', 'Exam window lost focus'),
                        ('fullscreen_exit', 'Fullscreen exited'),
                        ('inactivity', 'Extended inactivity'),
                        ('copy', 'Copy attempted'),
                        ('paste', 'Paste attempted'),
                        ('contextmenu', 'Right-click attempted'),
                        ('restricted_shortcut', 'Restricted keyboard shortcut'),
                        ('leave_attempt', 'Page leave / refresh attempted'),
                    ],
                    max_length=40,
                )),
                ('strike_number', models.PositiveSmallIntegerField(default=0)),
                ('client_occurred_at', models.DateTimeField(blank=True, null=True)),
                ('detail', models.JSONField(blank=True, default=dict)),
                ('classroom', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='sat.classroom',
                )),
                ('stage', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='integrity_events',
                    to='sat.teststage',
                )),
                ('test', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='sat.test',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sat_integrity_events',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['created_at', 'id']},
        ),
        migrations.AddIndex(
            model_name='examintegrityviolation',
            index=models.Index(fields=['user', 'attempt_id', 'created_at'], name='sat_eiv_u_att_cr'),
        ),
        migrations.AddIndex(
            model_name='examintegrityviolation',
            index=models.Index(fields=['classroom', 'test', 'created_at'], name='sat_eiv_cls_t_cr'),
        ),
    ]

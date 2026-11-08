from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import apps.sat.storages
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sat', '0043_user_chat_stickers_v523'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassroomLesson',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=220)),
                ('summary', models.TextField(blank=True)),
                ('order', models.PositiveIntegerField(db_index=True, default=1)),
                ('is_published', models.BooleanField(db_index=True, default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('classroom', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lessons', to='sat.classroom')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_classroom_lessons', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['order', 'created_at'], 'unique_together': {('classroom', 'order')}},
        ),
        migrations.CreateModel(
            name='ClassroomLessonResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=220)),
                ('resource_type', models.CharField(choices=[('file', 'File'), ('link', 'Link'), ('presentation', 'Presentation')], default='file', max_length=20)),
                ('file', models.FileField(blank=True, null=True, storage=apps.sat.storages.PublicStorage(), upload_to='classroom_lessons/%Y/%m/')),
                ('url', models.URLField(blank=True)),
                ('description', models.CharField(blank=True, max_length=300)),
                ('is_visible', models.BooleanField(db_index=True, default=True)),
                ('order', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='resources', to='sat.classroomlesson')),
            ],
            options={'ordering': ['order', 'created_at']},
        ),
        migrations.CreateModel(
            name='ClassroomHomeworkAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=220)),
                ('instructions', models.TextField(blank=True)),
                ('assignment_type', models.CharField(choices=[('sat_test', 'SAT test'), ('vocabulary_unit', 'Vocabulary unit')], max_length=24)),
                ('vocabulary_mode', models.CharField(choices=[('memory', 'Memory Layers'), ('animated-immersion', 'Animated Immersion'), ('word-bounce', 'Word Bounce'), ('meaning-match', 'Meaning Match')], default='memory', max_length=32)),
                ('question_count', models.PositiveSmallIntegerField(default=10, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)])),
                ('assign_all', models.BooleanField(default=True)),
                ('due_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_students', models.ManyToManyField(blank=True, related_name='classroom_homework', to=settings.AUTH_USER_MODEL)),
                ('classroom', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='homework_assignments', to='sat.classroom')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_homework_assignments', to=settings.AUTH_USER_MODEL)),
                ('test', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='classroom_homework_assignments', to='sat.test')),
                ('vocabulary_unit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='classroom_homework_assignments', to='sat.vocabularyunit')),
            ],
            options={'ordering': ['due_at', '-created_at']},
        ),
    ]

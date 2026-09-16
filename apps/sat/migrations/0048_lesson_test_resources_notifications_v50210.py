from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('sat', '0047_support_teacher_profile_sections_v529'),
    ]

    operations = [
        migrations.AddField(
            model_name='classroomlessonresource',
            name='access_code',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='classroomlessonresource',
            name='score_visibility',
            field=models.CharField(choices=[('hidden', 'Do not show classroom points'), ('immediate', 'Show classroom points immediately'), ('scheduled', 'Show classroom points on a scheduled date')], default='immediate', max_length=20),
        ),
        migrations.AddField(
            model_name='classroomlessonresource',
            name='score_visible_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='classroomlessonresource',
            name='test',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='classroom_lesson_resources', to='sat.test'),
        ),
        migrations.AddField(
            model_name='classroomlessonresource',
            name='total_points',
            field=models.PositiveSmallIntegerField(default=100, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10000)]),
        ),
        migrations.AlterField(
            model_name='classroomlessonresource',
            name='resource_type',
            field=models.CharField(choices=[('file', 'File'), ('link', 'Link'), ('presentation', 'Presentation'), ('test', 'SAT Test')], default='file', max_length=20),
        ),
        migrations.AlterField(
            model_name='makonnotification',
            name='type',
            field=models.CharField(choices=[('test_review', 'Test review'), ('test_published', 'Test published'), ('homework', 'Homework'), ('classroom', 'Classroom'), ('lesson', 'Lesson'), ('access', 'Access'), ('assessment', 'Assessment'), ('support', 'Support lesson')], max_length=32),
        ),
    ]

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('ratings', '0002_alter_ratingassessment_teacher'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TermGrade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('academic_year', models.CharField(help_text='E.g. 2026/2027', max_length=16)),
                ('term', models.CharField(choices=[('midterm', 'Mid-term'), ('final', 'Final-term')], max_length=15)),
                ('score', models.DecimalField(decimal_places=2, max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('maximum_score', models.PositiveSmallIntegerField(default=100, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)])),
                ('awarded_at', models.DateField(default=django.utils.timezone.localdate)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('classroom', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='term_grades', to='sat.classroom')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='term_grades', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-awarded_at', 'classroom__name', 'term']},
        ),
        migrations.AddConstraint(model_name='termgrade', constraint=models.UniqueConstraint(fields=('student', 'classroom', 'academic_year', 'term'), name='rating_unique_term_grade')),
    ]

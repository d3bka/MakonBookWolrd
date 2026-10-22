from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('sat', '0050_exam_integrity_v54'),
    ]

    operations = [
        migrations.AddField(
            model_name='teststage',
            name='mode',
            field=models.CharField(default='full_test', max_length=50),
        ),
    ]

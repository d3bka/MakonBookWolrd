from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('sat', '0055_teststage_mode_db_default_v5531'),
    ]

    operations = [
        migrations.AddField(
            model_name='test',
            name='test_type',
            field=models.CharField(
                choices=[
                    ('regular', 'Regular / Practice Test'),
                    ('placement', 'Placement Test'),
                    ('event', 'Event Test'),
                ],
                db_default='regular',
                db_index=True,
                default='regular',
                help_text=(
                    'Regular tests appear in Tests, Placement tests appear in Placement Tests, '
                    'and Event tests are used as event-only question banks. '
                    'Linking any test to GlobalEvent does not change this field.'
                ),
                max_length=20,
            ),
        ),
    ]

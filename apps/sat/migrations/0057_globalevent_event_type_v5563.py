from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('sat', '0056_test_test_type_v5560'),
    ]

    operations = [
        migrations.AddField(
            model_name='globalevent',
            name='event_type',
            field=models.CharField(
                'Event type',
                choices=[
                    ('event', 'Event'),
                    ('placement', 'Placement Test'),
                ],
                db_default='event',
                db_index=True,
                default='event',
                help_text=(
                    'Controls where this Global Event appears. '
                    'Event = Events page. Placement Test = Placement Tests page. '
                    'The linked source Test keeps its own Test Type.'
                ),
                max_length=20,
            ),
        ),
    ]

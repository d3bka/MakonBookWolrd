from django.db import migrations


def set_teststage_mode_default(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute("""
        ALTER TABLE sat_teststage
        ALTER COLUMN mode SET DEFAULT 'full_test';
    """)


def drop_teststage_mode_default(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute("""
        ALTER TABLE sat_teststage
        ALTER COLUMN mode DROP DEFAULT;
    """)


class Migration(migrations.Migration):
    dependencies = [
        ('sat', '0054_homework_integration_v553'),
    ]

    operations = [
        migrations.RunPython(
            set_teststage_mode_default,
            drop_teststage_mode_default,
        ),
    ]

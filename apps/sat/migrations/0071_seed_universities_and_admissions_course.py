from django.db import migrations


def seed(apps, schema_editor):
    from apps.sat.admissions_course import load_admissions_course
    from apps.sat.university_data import load_universities

    load_universities(apps.get_model("sat", "University"), update=False)
    load_admissions_course(
        apps.get_model("sat", "AdmissionsLesson"),
        apps.get_model("sat", "AdmissionsStep"),
        apps.get_model("sat", "AdmissionsResource"),
    )


class Migration(migrations.Migration):
    dependencies = [("sat", "0070_admissionslesson_university_admissionsresource_and_more")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

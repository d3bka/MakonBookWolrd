"""V81: replace the V80 text lessons with SATMakon's 28 video lessons and add the premium file records.

Only the V80 seed lessons (by slug) are touched. A V80 lesson whose slug the video course
reuses ("supplemental-essays") is updated in place, so its progress rows survive; the others
are removed. Lessons an admin created by hand stay.
Videos and PDF pages are not in the database: `manage.py import_admissions_media` adds them.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    from apps.sat.admissions_course import (
        LESSONS, V80_LESSON_SLUGS, load_admissions_course, load_admissions_documents,
    )

    Lesson = apps.get_model("sat", "AdmissionsLesson")
    Step = apps.get_model("sat", "AdmissionsStep")
    Resource = apps.get_model("sat", "AdmissionsResource")
    new_by_slug = {lesson["slug"]: lesson for lesson in LESSONS}

    Lesson.objects.filter(slug__in=[slug for slug in V80_LESSON_SLUGS if slug not in new_by_slug]).delete()
    for lesson in Lesson.objects.filter(slug__in=[slug for slug in V80_LESSON_SLUGS if slug in new_by_slug]):
        data = new_by_slug[lesson.slug]
        lesson.order, lesson.module, lesson.title = data["number"], data["module"], data["title"]
        lesson.summary, lesson.minutes = data["summary"], data["minutes"]
        lesson.save()
        Step.objects.filter(lesson=lesson).delete()
        Resource.objects.filter(lesson=lesson).delete()
        for order, (title, body) in enumerate(data["steps"], start=1):
            Step.objects.create(lesson=lesson, order=order, title=title, body=body)
        for order, (title, url, kind, note) in enumerate(data["resources"], start=1):
            Resource.objects.create(lesson=lesson, order=order, title=title, url=url, kind=kind, note=note)

    load_admissions_course(Lesson, Step, Resource)
    load_admissions_documents(apps.get_model("sat", "AdmissionsDocument"), Lesson)


class Migration(migrations.Migration):
    dependencies = [("sat", "0072_admissions_premium_media")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

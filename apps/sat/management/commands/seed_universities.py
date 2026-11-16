"""V80: load or refresh the Universities catalogue and the Admissions course seed.

    manage.py seed_universities            # add missing universities and lessons
    manage.py seed_universities --update   # also overwrite existing universities with the seed figures
"""
from django.core.management.base import BaseCommand

from apps.sat.admissions_course import load_admissions_course
from apps.sat.models import AdmissionsLesson, AdmissionsResource, AdmissionsStep, University
from apps.sat.university_data import load_universities


class Command(BaseCommand):
    help = "Load the V80 university catalogue and Admissions lessons (safe to re-run)."

    def add_arguments(self, parser):
        parser.add_argument("--update", action="store_true",
                            help="Overwrite existing universities (admin edits are lost).")

    def handle(self, *args, **options):
        created, updated = load_universities(University, update=options["update"])
        lessons = load_admissions_course(AdmissionsLesson, AdmissionsStep, AdmissionsResource)
        self.stdout.write(self.style.SUCCESS(
            f"Universities: {created} created, {updated} updated. Admissions lessons created: {lessons}."
        ))

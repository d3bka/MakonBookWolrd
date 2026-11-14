from django.core.management.base import BaseCommand

from apps.sat.models import TestReview


class Command(BaseCommand):
    help = "Forget every cached certificate PDF; each one is rebuilt on its next download."

    def handle(self, *args, **kwargs):
        cleared = TestReview.objects.exclude(certificate="").update(certificate="")
        self.stdout.write(self.style.SUCCESS(f"Cleared {cleared} cached certificate(s)."))

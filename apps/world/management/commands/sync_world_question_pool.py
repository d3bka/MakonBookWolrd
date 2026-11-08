from django.core.management.base import BaseCommand, CommandError

from apps.world.models import WorldRating
from apps.world.services import sync_question_pool


class Command(BaseCommand):
    help = "Build/refresh the curated MakonBook World question pool from structurally valid SAT questions."

    def add_arguments(self, parser):
        parser.add_argument("--subject", choices=[WorldRating.SUBJECT_MATH, WorldRating.SUBJECT_RW])
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        try:
            result = sync_question_pool(subject=options.get("subject"), limit=options.get("limit"))
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"World question pool synced: created={result['created']} updated={result['updated']} disabled={result['disabled']}"
        ))

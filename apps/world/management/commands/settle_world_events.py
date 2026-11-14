"""Pay rewards for ended World events (idempotent; safe to run from cron/beat)."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.world.events import ensure_seasonal_competition, settle
from apps.world.models import WorldEvent


class Command(BaseCommand):
    help = "Settle ended World events and make sure this season's cup exists."

    def add_arguments(self, parser):
        parser.add_argument("--no-season-cup", action="store_true", help="Do not create the seasonal competition.")

    def handle(self, *args, **options):
        now = timezone.now()
        settled = 0
        for event in WorldEvent.objects.filter(settled_at__isnull=True, ends_at__lte=now):
            rewarded = settle(event, now)
            settled += 1
            self.stdout.write(f"settled {event.title}: {rewarded} player(s) rewarded")
        if not options["no_season_cup"]:
            cup, created = ensure_seasonal_competition()
            self.stdout.write(f"season cup {cup.title}: {'created' if created else 'exists'}")
        self.stdout.write(self.style.SUCCESS(f"Settled {settled} event(s)."))

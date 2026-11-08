"""Daily operations; safe to rerun. Schedule Celery Beat or execute via cron."""
from django.core.management.base import BaseCommand
from apps.ratings.assessment_policy import (
    prepare_today_obligations, settle_missed_assessments,
    send_pending_daily_manager_reports,
)


class Command(BaseCommand):
    help = 'Prepare today\'s assessment roster, settle overdue obligations, notify managers.'

    def handle(self, *args, **options):
        # Prepare BEFORE settlement. These two operations never retro-create
        # missed days, even if cron was offline for a week.
        prepared = prepare_today_obligations()
        fines = settle_missed_assessments()
        sent = send_pending_daily_manager_reports()
        self.stdout.write(f'Prepared {prepared} obligations; issued {len(fines)} new fines; daily report sent={sent}.')

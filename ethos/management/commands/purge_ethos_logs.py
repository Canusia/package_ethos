"""Delete EthosLog rows past the retention window.

Nothing purged EthosLog before this command: the cis hourly cron's
purge_sis_logs / purge_sis_messages touch only the legacy SIS_Log and
SIS_Subscription models, so the Ethos call log grew without bound.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...consume import config
from ...models import EthosLog


class Command(BaseCommand):
    help = 'Delete Ethos API call logs past the retention window.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=None,
                            help='Retention window. Defaults to ETHOS_LOG_RETENTION_DAYS.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would be deleted. Deletes nothing.')

    def handle(self, *args, **options):
        days = options['days'] or config.log_retention_days()
        cutoff = timezone.now() - timedelta(days=days)
        qs = EthosLog.objects.filter(sent_on__lt=cutoff)

        count = qs.count()
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'would delete {count} log(s) older than {days} days'))
            return

        qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f'deleted {count} log(s) older than {days} days'))

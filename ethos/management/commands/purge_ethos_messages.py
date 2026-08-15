"""Delete EthosMessage rows past the retention window.

Deletion is outright — the consume result goes with the message. Anything needed
long-term must be captured by the handler (e.g. a note on the affected record),
not left in EthosMessage.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...consume import config
from ...models import EthosMessage


class Command(BaseCommand):
    help = 'Delete stored Ethos change-notifications past the retention window.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=None,
                            help='Retention window. Defaults to ETHOS_CONSUME_RETENTION_DAYS.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would be deleted. Deletes nothing.')

    def handle(self, *args, **options):
        days = options['days'] or config.retention_days()
        cutoff = timezone.now() - timedelta(days=days)
        qs = EthosMessage.objects.filter(received_on__lt=cutoff)

        count = qs.count()
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'would delete {count} message(s) older than {days} days'))
            return

        qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f'deleted {count} message(s) older than {days} days'))

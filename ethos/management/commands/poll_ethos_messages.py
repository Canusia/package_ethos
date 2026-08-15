"""Poll Ethos /consume and store change-notifications. Stores only; never consumes."""

from django.core.management.base import BaseCommand

from ...consume import config
from ...consume.poller import poll


class Command(BaseCommand):
    help = 'Poll the Ethos change-notification queue and store notifications.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=None,
                            help='Notifications per batch (Ethos allows 1-1000).')
        parser.add_argument('--max-batches', type=int, default=1,
                            help='How many batches to read this run.')
        parser.add_argument('--from-id', type=int, default=None,
                            help='Replay from this queue id, ignoring the stored cursor.')
        parser.add_argument('--peek', action='store_true',
                            help='HEAD /consume for queue depth. No side effects.')

    def handle(self, *args, **options):
        if options['peek']:
            from ...library.ethos import Ethos
            count = Ethos().available_message_count()
            self.stdout.write(f'{count} notification(s) queued')
            return

        result = poll(
            limit=options['limit'] or config.consume_limit(),
            max_batches=options['max_batches'],
            from_id=options['from_id'],
        )
        self.stdout.write(self.style.SUCCESS(
            f"stored={result['stored']} duplicates={result['duplicates']} "
            f"batches={result['batches']} last_id={result['last_id']}"
        ))

"""Consume stored change-notifications.

Selection rules, in order:
  --id            one message, regardless of auto-consume
  --resource      restrict to a resource name
  otherwise       pending messages whose resource has auto-consume enabled

Always processed in ascending queue_id order, but each message stands alone: a
failure does not block the next one.
"""

from django.core.management.base import BaseCommand

from ...consume import config
from ...consume.service import consume_message
from ...models import EthosMessage


class Command(BaseCommand):
    help = 'Consume stored Ethos change-notifications.'

    def add_arguments(self, parser):
        parser.add_argument('--id', type=int, default=None,
                            help='Process one EthosMessage by primary key.')
        parser.add_argument('--resource', default=None,
                            help='Restrict to one resource name.')
        parser.add_argument('--limit', type=int, default=None,
                            help='Max messages to process this run.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would happen. Writes nothing.')
        parser.add_argument('--force', action='store_true',
                            help='Process regardless of auto-consume, and re-run '
                                 'messages that are not pending.')

    def _queryset(self, options):
        if options['id'] is not None:
            return EthosMessage.objects.filter(pk=options['id'])

        qs = EthosMessage.objects.filter(status=EthosMessage.PENDING)
        if options['resource']:
            qs = qs.filter(resource_name=options['resource'])
        else:
            enabled = [r for r in qs.values_list('resource_name', flat=True).distinct()
                       if config.auto_consume_enabled(r)]
            qs = qs.filter(resource_name__in=enabled)
        return qs

    def handle(self, *args, **options):
        explicit = options['id'] is not None or bool(options['resource'])
        force = options['force'] or options['id'] is not None

        qs = self._queryset(options).order_by('queue_id')
        if options['limit']:
            qs = qs[:options['limit']]

        counts = {}
        for message in qs:
            if options['dry_run']:
                plan = consume_message(message, dry_run=True)
                if plan is None:
                    self.stdout.write(f'#{message.queue_id} no handler')
                    continue
                flag = ' [BLOCKED]' if plan.blocked else ''
                self.stdout.write(f'#{message.queue_id} {plan.action}{flag}: {plan.summary}')
                for change in plan.changes:
                    self.stdout.write(f'    {change.field}: {change.old} -> {change.new}')
                continue

            consume_message(message, force=force or explicit)
            message.refresh_from_db()
            counts[message.status] = counts.get(message.status, 0) + 1

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('dry run — nothing written'))
        else:
            summary = ' '.join(f'{k}={v}' for k, v in sorted(counts.items())) or 'nothing to do'
            self.stdout.write(self.style.SUCCESS(summary))

"""Poll Ethos /consume and store change-notifications.

Stores only. Consuming is a separate step — unless the operator has switched
"Consume After Polling" on in the Ethos Change Notifications setting, in which
case this command chains to `process_ethos_messages` after storing.

This is the command the CronTab row runs, so two things live here:

* the `is_active` gate — a scheduled run exits immediately when polling is
  switched off, which is what lets the cron row stay in place while the
  feature is dormant; and
* the `cron_task_started` / `cron_task_done` signals, which record the run in
  CronLog. They fire only when `--time` is supplied, which is how
  `cis.management.commands.cron_jobs` invokes scheduled commands — a manual run
  writes no CronLog entry.

A disabled or failed run still emits `cron_task_done`, so the log shows *why*
nothing happened rather than showing nothing at all.
"""

import json

from django.core.management import call_command
from django.core.management.base import BaseCommand

from cis.signals.crontab import cron_task_done, cron_task_started

from ...consume import config
from ...consume.poller import poll


class Command(BaseCommand):
    help = 'Poll the Ethos change-notification queue and store notifications.'

    def add_arguments(self, parser):
        parser.add_argument('-t', '--time', type=str, help='Time of run')
        parser.add_argument('--limit', type=int, default=None,
                            help='Notifications per request (Ethos allows 1-1000). '
                                 'Defaults to the configured setting.')
        parser.add_argument('--max-batches', type=int, default=None,
                            help='How many requests to make this run. '
                                 'Defaults to the configured setting.')
        parser.add_argument('--from-id', type=int, default=None,
                            help='Replay from this queue id, ignoring the stored cursor.')
        parser.add_argument('--peek', action='store_true',
                            help='HEAD /consume for queue depth. No side effects, and '
                                 'works even when polling is switched off.')
        parser.add_argument('--force', action='store_true',
                            help='Run even when polling is switched off. For manual '
                                 'verification before enabling the schedule.')

    def _done(self, scheduled_time, summary, detailed_log):
        if not scheduled_time:
            return
        cron_task_done.send(
            sender=self.__class__,
            task=self.__class__,
            scheduled_time=scheduled_time,
            summary=summary,
            detailed_log=json.dumps(detailed_log),
        )

    def handle(self, *args, **kwargs):
        # Peek is read-only and never advances Ethos's pointer, so it stays
        # available while the feature is off — it is the safe way to confirm the
        # subscription is wired before switching polling on. It is a manual
        # affordance, so it deliberately records no CronLog entry.
        if kwargs['peek']:
            from ...library.ethos import Ethos
            count = Ethos().available_message_count()
            self.stdout.write(f'{count} notification(s) queued')
            return

        scheduled_time = kwargs.get('time')
        if scheduled_time:
            cron_task_started.send(
                sender=self.__class__,
                task=self.__class__,
                scheduled_time=scheduled_time,
            )

        if not config.poll_enabled() and not kwargs['force']:
            summary = ('Ethos polling is switched off — enable it in Settings > '
                       'Ethos Change Notifications, or pass --force for a one-off run.')
            self.stdout.write(self.style.WARNING(summary))
            self._done(scheduled_time, summary, {'skipped': True, 'reason': 'polling disabled'})
            return

        detailed_log = {
            'limit': kwargs['limit'] or config.consume_limit(),
            'max_batches': kwargs['max_batches'] or config.max_batches(),
            'from_id': kwargs['from_id'],
            'forced': bool(kwargs['force']),
        }

        try:
            result = poll(
                limit=detailed_log['limit'],
                max_batches=detailed_log['max_batches'],
                from_id=detailed_log['from_id'],
            )
        except Exception as exc:
            # Ethos's pointer may already have advanced past notifications this
            # run failed to store, so the CronLog entry is part of the audit
            # trail for what was lost — record it, then let it surface.
            summary = f'Ethos poll FAILED: {exc}'
            detailed_log['error'] = str(exc)
            self._done(scheduled_time, summary, detailed_log)
            raise

        detailed_log.update(result)
        summary = (f"Stored {result['stored']} notification(s), "
                   f"{result['duplicates']} duplicate(s), across "
                   f"{result['batches']} batch(es); last id {result['last_id']}")
        self.stdout.write(self.style.SUCCESS(
            f"stored={result['stored']} duplicates={result['duplicates']} "
            f"batches={result['batches']} last_id={result['last_id']}"
        ))

        if not config.consume_after_poll():
            detailed_log['consumed_after_poll'] = False
            self._done(scheduled_time, summary, detailed_log)
            return

        # Runs regardless of how many were just stored: older pending messages
        # may be waiting, e.g. from a run before a handler was registered.
        # `process_ethos_messages` still honors the per-resource auto-consume
        # map, so this chain cannot consume a resource that is not opted in.
        detailed_log['consumed_after_poll'] = True
        self.stdout.write('Consuming newly stored notifications...')
        try:
            call_command('process_ethos_messages', stdout=self.stdout, stderr=self.stderr)
        except Exception as exc:
            summary += f' | consume step FAILED: {exc}'
            detailed_log['consume_error'] = str(exc)
            self._done(scheduled_time, summary, detailed_log)
            raise

        self._done(scheduled_time, summary, detailed_log)

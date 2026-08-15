"""The operator-facing poll setting: gate, ranges, fallback, cron sync, signals."""
import importlib.util
import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from cis.signals.crontab import cron_task_done, cron_task_started

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.consume import config
    from ethos.ethos.settings.ethos_consume import ethos_consume, POLL_COMMAND
else:  # pragma: no cover - flat pip layout
    from ethos.consume import config
    from ethos.settings.ethos_consume import ethos_consume, POLL_COMMAND

from cis.models.crontab import CronTab
from cis.models.settings import Setting
from . import PKG


def _seed(**overrides):
    value = {
        'is_active': 'No',
        'limit': 100,
        'max_batches': 1,
        'consume_after_poll': 'No',
        'cron': '0 * * * *',
    }
    value.update(overrides)
    Setting.objects.update_or_create(key=ethos_consume.key, defaults={'value': value})


class ReadHelperTests(TestCase):
    def test_defaults_are_inert_when_no_row_exists(self):
        """A fresh install must not poll until someone turns it on."""
        self.assertFalse(ethos_consume.is_poll_enabled())
        self.assertFalse(ethos_consume.consume_after_poll_enabled())

    def test_is_poll_enabled_reads_yes(self):
        _seed(is_active='Yes')
        self.assertTrue(ethos_consume.is_poll_enabled())

    def test_is_poll_enabled_is_case_insensitive(self):
        _seed(is_active='yes')
        self.assertTrue(ethos_consume.is_poll_enabled())

    def test_consume_after_poll_reads_yes(self):
        _seed(consume_after_poll='Yes')
        self.assertTrue(ethos_consume.consume_after_poll_enabled())

    def test_limit_and_batches_read_through(self):
        _seed(limit=250, max_batches=7)
        self.assertEqual(ethos_consume.get_limit(), 250)
        self.assertEqual(ethos_consume.get_max_batches(), 7)

    def test_limit_accepts_the_ethos_maximum(self):
        _seed(limit=1000)
        self.assertEqual(ethos_consume.get_limit(), 1000)

    def test_out_of_range_limit_is_rejected_not_clamped(self):
        """Out-of-range means 'unconfigured', so the caller falls back."""
        _seed(limit=5000)
        self.assertIsNone(ethos_consume.get_limit())

    def test_zero_limit_is_rejected(self):
        _seed(limit=0)
        self.assertIsNone(ethos_consume.get_limit())

    def test_non_numeric_limit_is_rejected(self):
        _seed(limit='lots')
        self.assertIsNone(ethos_consume.get_limit())

    def test_numeric_string_limit_is_accepted(self):
        """Form-posted values arrive as strings."""
        _seed(limit='250')
        self.assertEqual(ethos_consume.get_limit(), 250)


class ConfigPrecedenceTests(TestCase):
    @override_settings(ETHOS_CONSUME_LIMIT=42)
    def test_setting_wins_over_django_settings(self):
        _seed(limit=250)
        self.assertEqual(config.consume_limit(), 250)

    @override_settings(ETHOS_CONSUME_LIMIT=42)
    def test_falls_back_when_no_row_exists(self):
        self.assertEqual(config.consume_limit(), 42)

    @override_settings(ETHOS_CONSUME_LIMIT=42)
    def test_falls_back_when_value_is_out_of_range(self):
        _seed(limit=5000)
        self.assertEqual(config.consume_limit(), 42)

    def test_hardcoded_default_when_nothing_configured(self):
        self.assertEqual(config.consume_limit(), 100)
        self.assertEqual(config.max_batches(), 1)


class CronSyncTests(TestCase):
    def test_saving_upserts_a_single_cron_row(self):
        form = ethos_consume.__new__(ethos_consume)
        form.cleaned_data = {
            'is_active': 'Yes', 'limit': 100, 'max_batches': 1,
            'consume_after_poll': 'No', 'cron': '*/15 * * * *',
        }

        form._to_python()
        form.cleaned_data['cron'] = '0 2 * * *'
        form._to_python()

        rows = CronTab.objects.filter(command=POLL_COMMAND)
        self.assertEqual(rows.count(), 1, 'editing the schedule must move the job, not duplicate it')
        self.assertEqual(rows.first().cron, '0 2 * * *')


class PollCommandGateTests(TestCase):
    def test_exits_without_calling_ethos_when_disabled(self):
        _seed(is_active='No')
        out = StringIO()

        with patch(f'{PKG}.consume.poller.poll') as mock_poll:
            call_command('poll_ethos_messages', stdout=out)

        mock_poll.assert_not_called()
        self.assertIn('switched off', out.getvalue())

    def test_force_overrides_the_gate(self):
        _seed(is_active='No')

        with patch(f'{PKG}.management.commands.poll_ethos_messages.poll',
                   return_value={'stored': 0, 'duplicates': 0, 'batches': 1, 'last_id': None}) as mock_poll:
            call_command('poll_ethos_messages', '--force', stdout=StringIO())

        mock_poll.assert_called_once()

    def test_polls_when_enabled(self):
        _seed(is_active='Yes', limit=250, max_batches=3)

        with patch(f'{PKG}.management.commands.poll_ethos_messages.poll',
                   return_value={'stored': 2, 'duplicates': 0, 'batches': 1, 'last_id': 9}) as mock_poll:
            call_command('poll_ethos_messages', stdout=StringIO())

        self.assertEqual(mock_poll.call_args[1]['limit'], 250)
        self.assertEqual(mock_poll.call_args[1]['max_batches'], 3)

    def test_flags_override_the_configured_values(self):
        _seed(is_active='Yes', limit=250, max_batches=3)

        with patch(f'{PKG}.management.commands.poll_ethos_messages.poll',
                   return_value={'stored': 0, 'duplicates': 0, 'batches': 1, 'last_id': None}) as mock_poll:
            call_command('poll_ethos_messages', '--limit', '5', '--max-batches', '2',
                         stdout=StringIO())

        self.assertEqual(mock_poll.call_args[1]['limit'], 5)
        self.assertEqual(mock_poll.call_args[1]['max_batches'], 2)

    def test_peek_works_while_polling_is_off(self):
        """Peek is read-only, so it must stay usable before the feature is enabled."""
        _seed(is_active='No')
        out = StringIO()

        with patch(f'{PKG}.library.ethos.Ethos.available_message_count', return_value=27):
            call_command('poll_ethos_messages', '--peek', stdout=out)

        self.assertIn('27', out.getvalue())


class CronSignalTests(TestCase):
    """cron_task_started/done drive the CronLog UI.

    They fire only when --time is supplied, which is how cron_jobs invokes
    scheduled commands; a manual run should leave no CronLog entry.
    """

    def setUp(self):
        self.started = []
        self.done = []
        cron_task_started.connect(self._on_started)
        cron_task_done.connect(self._on_done)
        self.addCleanup(cron_task_started.disconnect, self._on_started)
        self.addCleanup(cron_task_done.disconnect, self._on_done)

    def _on_started(self, sender, **kw):
        self.started.append(kw)

    def _on_done(self, sender, **kw):
        self.done.append(kw)

    def _poll(self, *args, **stored):
        result = {'stored': 0, 'duplicates': 0, 'batches': 1, 'last_id': None}
        result.update(stored)
        with patch(f'{PKG}.management.commands.poll_ethos_messages.poll',
                   return_value=result):
            call_command('poll_ethos_messages', *args, stdout=StringIO())

    def test_manual_run_emits_no_signals(self):
        _seed(is_active='Yes')

        self._poll()

        self.assertEqual(self.started, [])
        self.assertEqual(self.done, [])

    def test_scheduled_run_emits_both(self):
        _seed(is_active='Yes')

        self._poll('--time', '2026-08-15 10:00:00', stored=3)

        self.assertEqual(len(self.started), 1)
        self.assertEqual(len(self.done), 1)
        self.assertEqual(self.started[0]['scheduled_time'], '2026-08-15 10:00:00')
        self.assertIn('Stored 3', self.done[0]['summary'])
        self.assertEqual(json.loads(self.done[0]['detailed_log'])['stored'], 3)

    def test_disabled_scheduled_run_still_reports_why(self):
        """A silent no-op would look identical to a broken cron."""
        _seed(is_active='No')

        with patch(f'{PKG}.management.commands.poll_ethos_messages.poll') as mock_poll:
            call_command('poll_ethos_messages', '--time', '2026-08-15 10:00:00', stdout=StringIO())

        mock_poll.assert_not_called()
        self.assertEqual(len(self.started), 1)
        self.assertEqual(len(self.done), 1)
        self.assertTrue(json.loads(self.done[0]['detailed_log'])['skipped'])

    def test_failed_run_records_the_error_then_raises(self):
        _seed(is_active='Yes')

        with patch(f'{PKG}.management.commands.poll_ethos_messages.poll',
                   side_effect=ValueError('queue exploded')):
            with self.assertRaises(ValueError):
                call_command('poll_ethos_messages', '--time', '2026-08-15 10:00:00',
                             stdout=StringIO())

        self.assertEqual(len(self.done), 1)
        self.assertIn('FAILED', self.done[0]['summary'])
        self.assertIn('queue exploded', json.loads(self.done[0]['detailed_log'])['error'])

    def test_peek_emits_no_signals(self):
        _seed(is_active='Yes')

        with patch(f'{PKG}.library.ethos.Ethos.available_message_count', return_value=0):
            call_command('poll_ethos_messages', '--peek', '--time', '2026-08-15 10:00:00',
                         stdout=StringIO())

        self.assertEqual(self.started, [])
        self.assertEqual(self.done, [])


class ConsumeAfterPollTests(TestCase):
    def _run(self):
        with patch(f'{PKG}.management.commands.poll_ethos_messages.poll',
                   return_value={'stored': 1, 'duplicates': 0, 'batches': 1, 'last_id': 1}), \
             patch(f'{PKG}.management.commands.poll_ethos_messages.call_command') as chained:
            call_command('poll_ethos_messages', stdout=StringIO())
        return chained

    def test_does_not_consume_by_default(self):
        _seed(is_active='Yes', consume_after_poll='No')

        chained = self._run()

        chained.assert_not_called()

    def test_consumes_when_switched_on(self):
        _seed(is_active='Yes', consume_after_poll='Yes')

        chained = self._run()

        self.assertEqual(chained.call_args[0][0], 'process_ethos_messages')

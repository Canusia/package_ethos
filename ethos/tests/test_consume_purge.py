"""Retention deletes rows outright, including their consume result."""
import importlib.util
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.models import EthosMessage, EthosLog
else:
    from ethos.models import EthosMessage, EthosLog


def _message_aged(queue_id, days):
    msg = EthosMessage.objects.create(
        queue_id=queue_id, resource_name='section-registrations',
        resource_id=f'g{queue_id}', operation='created', payload={},
    )
    # received_on is auto_now_add — override after the fact
    EthosMessage.objects.filter(pk=msg.pk).update(
        received_on=timezone.now() - timedelta(days=days))
    return msg


def _log_aged(days):
    log = EthosLog.objects.create(method='GET', url='https://x/y',
                                  message_type='test', response_status=200)
    EthosLog.objects.filter(pk=log.pk).update(
        sent_on=timezone.now() - timedelta(days=days))
    return log


class PurgeMessagesTests(TestCase):
    def test_deletes_only_rows_past_the_window(self):
        _message_aged(1, days=45)
        _message_aged(2, days=5)

        call_command('purge_ethos_messages', stdout=StringIO())

        self.assertEqual(list(EthosMessage.objects.values_list('queue_id', flat=True)), [2])

    @override_settings(ETHOS_CONSUME_RETENTION_DAYS=60)
    def test_honours_the_configured_window(self):
        _message_aged(1, days=45)

        call_command('purge_ethos_messages', stdout=StringIO())

        self.assertEqual(EthosMessage.objects.count(), 1)

    def test_days_flag_overrides_the_setting(self):
        _message_aged(1, days=10)

        call_command('purge_ethos_messages', '--days', '5', stdout=StringIO())

        self.assertEqual(EthosMessage.objects.count(), 0)

    def test_dry_run_deletes_nothing(self):
        _message_aged(1, days=45)

        out = StringIO()
        call_command('purge_ethos_messages', '--dry-run', stdout=out)

        self.assertEqual(EthosMessage.objects.count(), 1)
        self.assertIn('1', out.getvalue())


class PurgeLogsTests(TestCase):
    def test_deletes_only_rows_past_the_window(self):
        _log_aged(days=120)
        recent = _log_aged(days=5)

        call_command('purge_ethos_logs', stdout=StringIO())

        self.assertEqual(list(EthosLog.objects.values_list('pk', flat=True)), [recent.pk])

    def test_dry_run_deletes_nothing(self):
        _log_aged(days=120)

        call_command('purge_ethos_logs', '--dry-run', stdout=StringIO())

        self.assertEqual(EthosLog.objects.count(), 1)

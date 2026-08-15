"""Selection rules for process_ethos_messages."""
import importlib.util
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.models import EthosMessage
else:
    from ethos.models import EthosMessage

from .test_consume_service import RecordingHandler, APPLIED  # noqa: F401

HANDLERS = {'section-registrations':
            'ethos.ethos.tests.test_consume_service.RecordingHandler'}


def _message(queue_id, **kwargs):
    defaults = dict(queue_id=queue_id, resource_name='section-registrations',
                    resource_id=f'guid-{queue_id}', operation='replaced', payload={})
    defaults.update(kwargs)
    return EthosMessage.objects.create(**defaults)


class ProcessCommandTests(TestCase):
    def setUp(self):
        APPLIED.clear()

    @override_settings(ETHOS_CONSUME_HANDLERS=HANDLERS)
    def test_leaves_messages_pending_when_auto_consume_is_off(self):
        _message(1)
        call_command('process_ethos_messages', stdout=StringIO())

        self.assertEqual(EthosMessage.objects.get(queue_id=1).status,
                         EthosMessage.PENDING)
        self.assertEqual(APPLIED, [])

    @override_settings(ETHOS_CONSUME_HANDLERS=HANDLERS,
                       ETHOS_CONSUME_AUTO={'section-registrations': True})
    def test_consumes_when_auto_consume_is_on(self):
        _message(1)
        call_command('process_ethos_messages', stdout=StringIO())

        self.assertEqual(EthosMessage.objects.get(queue_id=1).status,
                         EthosMessage.CONSUMED)

    @override_settings(ETHOS_CONSUME_HANDLERS=HANDLERS)
    def test_explicit_id_consumes_despite_auto_being_off(self):
        msg = _message(1)
        call_command('process_ethos_messages', '--id', str(msg.pk), stdout=StringIO())

        self.assertEqual(EthosMessage.objects.get(pk=msg.pk).status,
                         EthosMessage.CONSUMED)

    @override_settings(ETHOS_CONSUME_HANDLERS=HANDLERS)
    def test_dry_run_writes_nothing(self):
        _message(1)
        call_command('process_ethos_messages', '--resource', 'section-registrations',
                     '--dry-run', stdout=StringIO())

        self.assertEqual(EthosMessage.objects.get(queue_id=1).status,
                         EthosMessage.PENDING)
        self.assertEqual(APPLIED, [])

    @override_settings(ETHOS_CONSUME_HANDLERS=HANDLERS,
                       ETHOS_CONSUME_AUTO={'section-registrations': True})
    def test_processes_in_ascending_queue_order(self):
        _message(3)
        _message(1)
        _message(2)

        call_command('process_ethos_messages', stdout=StringIO())

        applied_order = [EthosMessage.objects.get(pk=pk).queue_id for pk in APPLIED]
        self.assertEqual(applied_order, [1, 2, 3])
        self.assertEqual(len(applied_order), 3)

    @override_settings(ETHOS_CONSUME_HANDLERS=HANDLERS)
    def test_resource_filter_limits_selection(self):
        _message(1)
        _message(2, resource_name='courses')

        call_command('process_ethos_messages', '--resource', 'section-registrations',
                     '--force', stdout=StringIO())

        self.assertEqual(EthosMessage.objects.get(queue_id=1).status,
                         EthosMessage.CONSUMED)
        self.assertEqual(EthosMessage.objects.get(queue_id=2).status,
                         EthosMessage.PENDING)

    @override_settings(ETHOS_CONSUME_HANDLERS=HANDLERS)
    def test_bare_force_consumes_despite_auto_consume_off(self):
        _message(1)
        call_command('process_ethos_messages', '--force', stdout=StringIO())

        self.assertEqual(EthosMessage.objects.get(queue_id=1).status,
                         EthosMessage.CONSUMED)

    @override_settings(ETHOS_CONSUME_HANDLERS=HANDLERS)
    def test_force_reruns_a_failed_message(self):
        msg = _message(1, status=EthosMessage.FAILED)
        call_command('process_ethos_messages', '--force', stdout=StringIO())

        self.assertEqual(EthosMessage.objects.get(pk=msg.pk).status,
                         EthosMessage.CONSUMED)

    @override_settings(ETHOS_CONSUME_HANDLERS=HANDLERS)
    def test_resource_filter_without_force_leaves_consumed_message_untouched(self):
        msg = _message(1, status=EthosMessage.CONSUMED)
        call_command('process_ethos_messages', '--resource', 'section-registrations',
                     stdout=StringIO())

        self.assertEqual(EthosMessage.objects.get(pk=msg.pk).status,
                         EthosMessage.CONSUMED)
        self.assertEqual(APPLIED, [])

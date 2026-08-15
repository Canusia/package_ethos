"""Model-level guarantees for the consume pipeline."""
import importlib.util

from django.test import TestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.models import EthosMessage, EthosConsumeCursor
else:
    from ethos.models import EthosMessage, EthosConsumeCursor


class EthosMessageTests(TestCase):
    def test_defaults_to_pending(self):
        msg = EthosMessage.objects.create(
            queue_id=1, resource_name='section-registrations',
            resource_id='guid-1', operation='created', payload={},
        )
        self.assertEqual(msg.status, EthosMessage.PENDING)
        self.assertTrue(msg.is_pending)
        self.assertIsNone(msg.consumed_at)

    def test_ordering_is_newest_queue_id_first(self):
        for qid in (1, 3, 2):
            EthosMessage.objects.create(
                queue_id=qid, resource_name='r', resource_id='g',
                operation='created', payload={},
            )
        self.assertEqual(
            list(EthosMessage.objects.values_list('queue_id', flat=True)),
            [3, 2, 1],
        )

    def test_status_reason_reads_from_payload(self):
        msg = EthosMessage.objects.create(
            queue_id=1, resource_name='section-registrations', resource_id='g',
            operation='created',
            payload={'content': {'status': {'sectionRegistrationStatusReason': 'dropped'}}},
        )
        self.assertEqual(msg.status_reason, 'dropped')

    def test_status_reason_is_blank_when_absent(self):
        msg = EthosMessage.objects.create(
            queue_id=1, resource_name='courses', resource_id='g',
            operation='created', payload={'content': {}},
        )
        self.assertEqual(msg.status_reason, '')


class EthosConsumeCursorTests(TestCase):
    def test_load_creates_singleton_starting_at_zero(self):
        cursor = EthosConsumeCursor.load()
        self.assertEqual(cursor.last_processed_id, 0)
        self.assertEqual(EthosConsumeCursor.objects.count(), 1)

    def test_load_is_idempotent(self):
        first = EthosConsumeCursor.load()
        first.last_processed_id = 27
        first.save()

        second = EthosConsumeCursor.load()
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(second.last_processed_id, 27)
        self.assertEqual(EthosConsumeCursor.objects.count(), 1)

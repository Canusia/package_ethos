"""The poller stores notifications and advances the cursor — never consumes."""
import importlib.util
import json
import os
from unittest.mock import MagicMock

from django.test import TestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.consume.poller import poll
    from ethos.ethos.models import EthosMessage, EthosConsumeCursor
else:
    from ethos.consume.poller import poll
    from ethos.models import EthosMessage, EthosConsumeCursor

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures',
                       'ctc-section-registration-notifications.json')


def load_sample():
    with open(FIXTURE) as fh:
        return json.load(fh)


def fake_client(batches, remaining=0):
    """A client whose get_messages returns each batch in turn."""
    client = MagicMock()
    client.get_messages.side_effect = [(b, MagicMock()) for b in batches]
    client.available_message_count.return_value = remaining
    return client


class PollerTests(TestCase):
    def setUp(self):
        self.sample = load_sample()

    def test_stores_every_notification_as_pending(self):
        result = poll(client=fake_client([self.sample]), limit=100)

        self.assertEqual(result['stored'], 27)
        self.assertEqual(EthosMessage.objects.count(), 27)
        self.assertEqual(
            EthosMessage.objects.filter(status=EthosMessage.PENDING).count(), 27)

    def test_stores_unhandled_resources_as_pending_not_skipped(self):
        """Handler existence is a consume-time question. Marking at capture would
        strand messages whose handler is registered later."""
        raw = dict(self.sample[0])
        raw['resource'] = dict(raw['resource'], name='courses')

        poll(client=fake_client([[raw]]), limit=100)

        msg = EthosMessage.objects.get(resource_name='courses')
        self.assertEqual(msg.status, EthosMessage.PENDING)

    def test_advances_cursor_to_highest_queue_id(self):
        poll(client=fake_client([self.sample]), limit=100)

        self.assertEqual(EthosConsumeCursor.load().last_processed_id, 27)

    def test_sends_stored_cursor_on_next_poll(self):
        client = fake_client([self.sample[:5], self.sample[5:10]])

        poll(client=client, limit=100)
        poll(client=client, limit=100)

        second_call_kwargs = client.get_messages.call_args_list[1][1]
        self.assertEqual(second_call_kwargs['last_processed_id'], 5)

    def test_duplicate_queue_ids_are_ignored(self):
        client = fake_client([self.sample, self.sample])

        poll(client=client, limit=100)
        result = poll(client=client, limit=100)

        self.assertEqual(EthosMessage.objects.count(), 27)
        self.assertEqual(result['duplicates'], 27)

    def test_cursor_unchanged_when_persist_fails(self):
        """A crash mid-batch must be replayable from the unchanged cursor."""
        bad = dict(self.sample[0])
        bad['id'] = 'not-a-number'
        client = fake_client([[self.sample[0], bad]])

        with self.assertRaises(ValueError):
            poll(client=client, limit=100)

        self.assertEqual(EthosConsumeCursor.load().last_processed_id, 0)
        self.assertEqual(EthosMessage.objects.count(), 0)

    def test_from_id_overrides_the_cursor(self):
        client = fake_client([self.sample])

        poll(client=client, limit=100, from_id=0)

        self.assertEqual(client.get_messages.call_args[1]['last_processed_id'], 0)

    def test_empty_batch_leaves_cursor_alone(self):
        EthosConsumeCursor.load()
        result = poll(client=fake_client([[]]), limit=100)

        self.assertEqual(result['stored'], 0)
        self.assertEqual(EthosConsumeCursor.load().last_processed_id, 0)

    def test_drains_multiple_batches_up_to_max(self):
        client = fake_client([self.sample[:10], self.sample[10:20]], remaining=7)

        result = poll(client=client, limit=10, max_batches=2)

        self.assertEqual(result['batches'], 2)
        self.assertEqual(result['stored'], 20)

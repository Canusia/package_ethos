"""The poller stores notifications and advances the cursor — never consumes."""
import importlib.util
import json
import os
from unittest.mock import MagicMock, patch

from django.test import TestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.consume.poller import poll
    from ethos.ethos.models import EthosMessage, EthosConsumeCursor
    import ethos.ethos.models as models_mod
else:
    from ethos.consume.poller import poll
    from ethos.models import EthosMessage, EthosConsumeCursor
    import ethos.models as models_mod

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

    def test_malformed_queue_id_still_stores_the_good_records_in_the_batch(self):
        """A record whose id can't be parsed as an int must not cost the other,
        well-formed records in the batch — Ethos has already advanced its
        pointer past all of them. The good record is stored, the cursor
        advances to cover it, and the caller still learns loudly (ValueError)
        that one record was malformed."""
        bad = dict(self.sample[0])
        bad['id'] = 'not-a-number'
        good = self.sample[1]
        client = fake_client([[good, bad]])

        with self.assertRaises(ValueError):
            poll(client=client, limit=100)

        self.assertEqual(EthosMessage.objects.count(), 1)
        self.assertEqual(EthosMessage.objects.get().queue_id, int(good['id']))
        self.assertEqual(EthosConsumeCursor.load().last_processed_id, int(good['id']))

    def test_malformed_record_is_logged_and_raised_after_good_records_persist(self):
        """Both properties must hold: the good record is committed, AND the
        operator is told loudly (via the raised error) that a record was
        dropped — not silently swallowed."""
        bad = dict(self.sample[2])
        bad['id'] = 'also-not-a-number'
        good = self.sample[3]
        client = fake_client([[good, bad]])

        with self.assertRaisesMessage(ValueError, 'malformed notification'):
            poll(client=client, limit=100)

        self.assertTrue(EthosMessage.objects.filter(queue_id=int(good['id'])).exists())

    def test_transaction_rolls_back_first_row_when_cursor_save_fails(self):
        """A failure that happens genuinely mid-batch — after at least one row
        has already been written — must still leave zero trace: the write and
        the cursor advance are one atomic unit, so a crash before commit
        replays cleanly from the unchanged cursor."""
        EthosConsumeCursor.load()  # materialize the singleton row before we
                                    # patch save(), or the read-side load()
                                    # inside poll() would trip the patch first.
        client = fake_client([self.sample[:2]])

        with patch.object(models_mod.EthosConsumeCursor, 'save',
                           side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                poll(client=client, limit=100)

        self.assertEqual(EthosMessage.objects.count(), 0)
        self.assertEqual(EthosConsumeCursor.load().last_processed_id, 0)

    def test_from_id_overrides_the_cursor(self):
        cursor = EthosConsumeCursor.load()
        cursor.last_processed_id = 50
        cursor.save()
        client = fake_client([self.sample])

        poll(client=client, limit=100, from_id=0)

        self.assertEqual(client.get_messages.call_args[1]['last_processed_id'], 0)

    def test_empty_batch_leaves_cursor_alone(self):
        cursor = EthosConsumeCursor.load()
        cursor.last_processed_id = 42
        cursor.save()
        result = poll(client=fake_client([[]]), limit=100)

        self.assertEqual(result['stored'], 0)
        self.assertEqual(EthosConsumeCursor.load().last_processed_id, 42)

    def test_replay_range_carries_local_high_water_mark_across_batches(self):
        """--from-id is the documented recovery mechanism for a queue whose
        pointer has already advanced past the stored cursor. Each subsequent
        batch in the same poll() call must continue from where the previous
        batch left off, not jump back to the (far-ahead) stored cursor."""
        cursor = EthosConsumeCursor.load()
        cursor.last_processed_id = 100
        cursor.save()
        client = fake_client([self.sample[:5], self.sample[5:10]])

        # limit=5 matches the first batch's size exactly, so the poller treats
        # it as a full page and continues to the second batch (the len(records)
        # < limit early-exit only fires on a short page).
        poll(client=client, limit=5, from_id=5, max_batches=2)

        second_call_kwargs = client.get_messages.call_args_list[1][1]
        self.assertEqual(second_call_kwargs['last_processed_id'], 5)

    def test_drains_multiple_batches_up_to_max(self):
        client = fake_client([self.sample[:10], self.sample[10:20]], remaining=7)

        result = poll(client=client, limit=10, max_batches=2)

        self.assertEqual(result['batches'], 2)
        self.assertEqual(result['stored'], 20)

"""package_ethos#5: one oversize envelope value must not wedge the queue."""
import importlib.util
import json
import os
from unittest.mock import MagicMock

from django.test import SimpleTestCase, TestCase, override_settings

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.consume.adapter import parse_notification
    from ethos.ethos.consume.poller import poll
    from ethos.ethos.models import EthosMessage, EthosConsumeCursor
else:
    from ethos.consume.adapter import parse_notification
    from ethos.consume.poller import poll
    from ethos.models import EthosMessage, EthosConsumeCursor

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures',
                       'ctc-section-registration-notifications.json')

# The shape RVC's Colleague sent on notification 460 (290 chars).
LONG_MESSAGE_ID = ('INSTITUTIONS.ATTEND*0582592*0525341,,INSTA.TRANSCRIPT.STATUS,AD guid,'
                   'INSTA.TRANSCRIPT.DATE,INSTA.TRANSCRIPT.TYPE,INSTITU').ljust(290, 'X')


def _sample():
    with open(FIXTURE) as fh:
        return json.load(fh)


def _client(batch):
    client = MagicMock()
    client.campus = None
    client.get_messages.side_effect = [(batch, MagicMock())]
    client.available_message_count.return_value = 0
    return client


@override_settings(MULTI_CAMPUS=False)
class LongEnvelopeStorageTests(TestCase):
    def test_long_message_id_is_stored_and_batch_commits(self):
        batch = _sample()
        batch[3] = dict(batch[3], messageId=LONG_MESSAGE_ID)

        result = poll(client=_client(batch), limit=100)

        self.assertEqual(result['stored'], len(batch))
        msg = EthosMessage.objects.get(queue_id=batch[3]['id'])
        self.assertEqual(msg.sis_message_id, LONG_MESSAGE_ID)
        self.assertEqual(EthosConsumeCursor.load().last_processed_id, max(int(r['id']) for r in batch))

    def test_oversize_bounded_fields_do_not_wedge_the_batch(self):
        batch = _sample()
        raw = dict(batch[0], contentType='c' * 80, messageType='m' * 80, operation='o' * 40,
                   publisher=dict(batch[0].get('publisher') or {}, id='p' * 100))
        raw['resource'] = dict(raw['resource'], id='r' * 100, version='v' * 300)
        batch[0] = raw

        result = poll(client=_client(batch), limit=100)

        self.assertEqual(result['stored'], len(batch))
        msg = EthosMessage.objects.get(queue_id=raw['id'])
        self.assertEqual(msg.payload, raw)  # verbatim, nothing lost


class AdapterBoundsTests(SimpleTestCase):
    def test_bounded_fields_fit_their_columns(self):
        raw = {'id': 1, 'operation': 'o' * 40, 'contentType': 'c' * 80, 'messageType': 'm' * 80,
               'messageId': LONG_MESSAGE_ID, 'publisher': {'id': 'p' * 100},
               'resource': {'name': 'n' * 200, 'id': 'r' * 100, 'version': 'v' * 300}}
        fields = parse_notification(raw)
        for name, value in fields.items():
            max_length = EthosMessage._meta.get_field(name).max_length
            if max_length and isinstance(value, str):
                self.assertLessEqual(len(value), max_length, name)
        self.assertEqual(fields['sis_message_id'], LONG_MESSAGE_ID)
        self.assertEqual(fields['payload'], raw)

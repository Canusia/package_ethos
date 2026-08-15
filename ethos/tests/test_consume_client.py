"""Client access to the Ethos change-notification queue."""
import importlib.util
from unittest.mock import MagicMock, patch

from django.test import TestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
    from ethos.ethos.models import EthosLog
else:
    from ethos.library.ethos import Ethos
    from ethos.models import EthosLog

CONSUME_ACCEPT = 'application/vnd.hedtech.change-notifications.v2+json'


def _resp(status=200, payload=None, headers=None, text='[]'):
    resp = MagicMock()
    resp.ok = 200 <= status < 300
    resp.status_code = status
    resp.headers = headers or {}
    resp.text = text
    resp.json.return_value = payload if payload is not None else []
    return resp


class GetMessagesTests(TestCase):
    def setUp(self):
        self.ethos = Ethos()

    def test_requests_consume_with_limit_and_cursor(self):
        with patch.object(self.ethos, 'get_auth_token', return_value='tok'), \
             patch('requests.get', return_value=_resp(payload=[{'id': '1'}])) as m:
            records, log = self.ethos.get_messages(limit=50, last_processed_id=7)

        url = m.call_args[0][0]
        self.assertIn('/consume', url)
        self.assertIn('limit=50', url)
        self.assertIn('lastProcessedID=7', url)
        self.assertEqual(m.call_args[1]['headers']['Accept'], CONSUME_ACCEPT)
        self.assertEqual(records, [{'id': '1'}])

    def test_omits_cursor_when_not_given(self):
        with patch.object(self.ethos, 'get_auth_token', return_value='tok'), \
             patch('requests.get', return_value=_resp()) as m:
            self.ethos.get_messages(limit=10)

        self.assertNotIn('lastProcessedID', m.call_args[0][0])

    def test_zero_cursor_is_sent(self):
        """lastProcessedID=0 is a meaningful replay-from-start, not 'absent'."""
        with patch.object(self.ethos, 'get_auth_token', return_value='tok'), \
             patch('requests.get', return_value=_resp()) as m:
            self.ethos.get_messages(limit=10, last_processed_id=0)

        self.assertIn('lastProcessedID=0', m.call_args[0][0])

    def test_writes_an_ethos_log(self):
        with patch.object(self.ethos, 'get_auth_token', return_value='tok'), \
             patch('requests.get', return_value=_resp()):
            records, log = self.ethos.get_messages(limit=10)

        self.assertIsInstance(log, EthosLog)
        self.assertEqual(log.message_type, 'change_notifications')
        self.assertEqual(EthosLog.objects.count(), 1)

    def test_returns_empty_list_on_error(self):
        with patch.object(self.ethos, 'get_auth_token', return_value='tok'), \
             patch('requests.get', return_value=_resp(status=500, text='boom')):
            records, log = self.ethos.get_messages(limit=10)

        self.assertEqual(records, [])
        self.assertEqual(log.response_status, 500)

    def test_raises_on_200_with_unparseable_body(self):
        """A 200 that fails to parse as JSON still means Ethos's queue pointer
        has already advanced — this must never be indistinguishable from an
        empty queue, so it must raise rather than return []."""
        resp = _resp(status=200, text='not json')
        resp.json.side_effect = ValueError('no JSON object could be decoded')
        with patch.object(self.ethos, 'get_auth_token', return_value='tok'), \
             patch('requests.get', return_value=resp):
            with self.assertRaises(ValueError):
                self.ethos.get_messages(limit=10)


class AvailableMessageCountTests(TestCase):
    def setUp(self):
        self.ethos = Ethos()

    def test_reads_x_remaining_header_via_head(self):
        with patch.object(self.ethos, 'get_auth_token', return_value='tok'), \
             patch('requests.head', return_value=_resp(headers={'x-remaining': '27'})) as m:
            count = self.ethos.available_message_count()

        self.assertEqual(count, 27)
        self.assertIn('/consume', m.call_args[0][0])

    def test_missing_header_is_zero(self):
        with patch.object(self.ethos, 'get_auth_token', return_value='tok'), \
             patch('requests.head', return_value=_resp(headers={})):
            self.assertEqual(self.ethos.available_message_count(), 0)

    def test_raises_rather_than_under_reporting_on_error_status(self):
        """--peek is the one side-effect-free primitive an operator has for
        checking queue depth; on a failed request (e.g. bad credentials) it
        must never silently report 0 as if the queue were empty."""
        with patch.object(self.ethos, 'get_auth_token', return_value='tok'), \
             patch('requests.head', return_value=_resp(status=401, headers={'x-remaining': '5'})):
            with self.assertRaises(ValueError):
                self.ethos.available_message_count()


class ApiRequestMethodTests(TestCase):
    def test_unsupported_method_raises_clearly(self):
        ethos = Ethos()
        with patch.object(ethos, 'get_auth_token', return_value='tok'):
            with self.assertRaises(ValueError):
                ethos._api_request('TRACE', 'https://example.test/x', 'test')

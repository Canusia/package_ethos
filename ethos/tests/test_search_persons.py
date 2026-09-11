import importlib.util
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
else:
    from ethos.library.ethos import Ethos

RECORD_A = {'id': 'guid-a', 'credentials': [{'type': 'bannerId', 'value': 'B1'}]}
RECORD_B = {'id': 'guid-b', 'credentials': [{'type': 'bannerId', 'value': 'B2'}]}


def _ok(payload):
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = payload
    return (resp, None)


def _not_ok():
    resp = MagicMock()
    resp.ok = False
    return (resp, None)


class SearchPersonsTests(SimpleTestCase):
    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_returns_every_matching_record(self, mock_api, _accept):
        mock_api.return_value = _ok([RECORD_A, RECORD_B])
        out = Ethos().search_persons({'names': [{'lastName': 'Doe'}]})
        self.assertEqual(out, [RECORD_A, RECORD_B])

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_no_match_returns_empty_list(self, mock_api, _accept):
        mock_api.return_value = _ok([])
        self.assertEqual(Ethos().search_persons({'names': [{'lastName': 'Doe'}]}), [])

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_failed_request_returns_empty_list(self, mock_api, _accept):
        mock_api.return_value = _not_ok()
        self.assertEqual(Ethos().search_persons({'names': [{'lastName': 'Doe'}]}), [])

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_non_list_payload_returns_empty_list(self, mock_api, _accept):
        mock_api.return_value = _ok({'id': 'guid-a'})
        self.assertEqual(Ethos().search_persons({'names': [{'lastName': 'Doe'}]}), [])

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_sends_criteria_on_the_persons_url(self, mock_api, _accept):
        mock_api.return_value = _ok([RECORD_A])
        Ethos().search_persons({'names': [{'lastName': 'Doe'}]})
        url = mock_api.call_args.args[1]
        self.assertIn('/api/persons?', url)
        self.assertIn('lastName', url)
        self.assertIn('Doe', url)

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_default_message_type_is_search_persons(self, mock_api, _accept):
        mock_api.return_value = _ok([RECORD_A])
        Ethos().search_persons({'names': [{'lastName': 'Doe'}]})
        self.assertEqual(mock_api.call_args.args[2], 'search_persons')


class LookupPersonRecordStillReturnsFirstTests(SimpleTestCase):
    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_returns_first_of_several(self, mock_api, _accept):
        mock_api.return_value = _ok([RECORD_A, RECORD_B])
        out = Ethos()._lookup_person_record({'names': [{'lastName': 'Doe'}]}, 'msg')
        self.assertEqual(out, RECORD_A)

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_empty_returns_none(self, mock_api, _accept):
        mock_api.return_value = _ok([])
        self.assertIsNone(
            Ethos()._lookup_person_record({'names': [{'lastName': 'Doe'}]}, 'msg'))

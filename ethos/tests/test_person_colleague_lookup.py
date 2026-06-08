import importlib.util
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
else:
    from ethos.library.ethos import Ethos

SAMPLE = [{
    "id": "66fcc15c-254d-4565-b08a-d2d6052d8b0d",
    "names": [{"type": {"category": "legal"},
               "firstName": "Life", "middleName": "Pacific", "lastName": "College"}],
    "credentials": [{"type": "colleaguePersonId", "value": "0000682"}],
}]


class ColleagueLookupTests(SimpleTestCase):
    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_returns_first_record(self, mock_api, _accept):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = SAMPLE
        mock_api.return_value = (resp, None)

        out = Ethos().lookup_person_by_colleague_person_id('0000682')

        self.assertEqual(out['id'], '66fcc15c-254d-4565-b08a-d2d6052d8b0d')
        # The criteria must target the colleaguePersonId credential.
        url_arg = mock_api.call_args.args[1]
        self.assertIn('colleaguePersonId', url_arg)
        self.assertIn('0000682', url_arg)

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_not_ok_returns_none(self, mock_api, _accept):
        resp = MagicMock()
        resp.ok = False
        mock_api.return_value = (resp, None)
        self.assertIsNone(Ethos().lookup_person_by_colleague_person_id('x'))

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_empty_list_returns_none(self, mock_api, _accept):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = []
        mock_api.return_value = (resp, None)
        self.assertIsNone(Ethos().lookup_person_by_colleague_person_id('x'))

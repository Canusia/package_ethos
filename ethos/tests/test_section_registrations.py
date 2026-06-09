import importlib.util
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
else:
    from ethos.library.ethos import Ethos

SECTION_ID = 'd74612f7-1c9c-47c4-8d60-17d730d70fa1'
REGISTRANT_ID = '0139d46b-8035-4bab-8c4d-384b6732fbf3'
SAMPLE = [
    {'registrant': {'id': 'r1'}, 'section': {'id': SECTION_ID},
     'status': {'registrationStatus': 'registered'}, 'id': 'reg1'},
    {'registrant': {'id': 'r2'}, 'section': {'id': SECTION_ID},
     'status': {'registrationStatus': 'notRegistered',
                'sectionRegistrationStatusReason': 'dropped'}, 'id': 'reg2'},
]


def _ok():
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = SAMPLE
    return (resp, None)


def _fail():
    resp = MagicMock()
    resp.ok = False
    resp.status_code = 500
    resp.text = 'boom'
    return (resp, None)


class GetSectionRegistrationsTests(SimpleTestCase):
    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_returns_list_on_ok(self, mock_api, _accept):
        mock_api.return_value = _ok()
        self.assertEqual(Ethos().get_section_registrations(SECTION_ID), SAMPLE)

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_sends_section_criteria(self, mock_api, _accept):
        mock_api.return_value = _ok()
        Ethos().get_section_registrations(SECTION_ID)
        url = mock_api.call_args.args[1]
        self.assertIn(SECTION_ID, url)
        self.assertNotIn('registrant', url)   # section criteria, not registrant

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_returns_empty_list_on_failure(self, mock_api, _accept):
        mock_api.return_value = _fail()
        self.assertEqual(Ethos().get_section_registrations(SECTION_ID), [])


class GetRegistrationsForRegistrantTests(SimpleTestCase):
    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_returns_list_on_ok(self, mock_api, _accept):
        mock_api.return_value = _ok()
        self.assertEqual(
            Ethos().get_registrations_for_registrant(REGISTRANT_ID), SAMPLE)

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_sends_registrant_criteria(self, mock_api, _accept):
        mock_api.return_value = _ok()
        Ethos().get_registrations_for_registrant(REGISTRANT_ID)
        url = mock_api.call_args.args[1]
        self.assertIn('registrant', url)
        self.assertIn(REGISTRANT_ID, url)

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_returns_empty_list_on_failure(self, mock_api, _accept):
        mock_api.return_value = _fail()
        self.assertEqual(
            Ethos().get_registrations_for_registrant(REGISTRANT_ID), [])

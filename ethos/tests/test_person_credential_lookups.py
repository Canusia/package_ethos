import importlib.util
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
else:
    from ethos.library.ethos import Ethos

# A record that exercises _extract_credential (bannerId/bannerUserName) and the
# email-type scan (personal vs school).
RECORD = {
    'id': 'guid-1',
    'credentials': [
        {'type': 'bannerId', 'value': 'B123'},
        {'type': 'bannerUserName', 'value': 'jdoe'},
    ],
    'emails': [
        {'type': {'emailType': 'personal'}, 'address': 'jdoe@home.com'},
        {'type': {'emailType': 'school'}, 'address': 'jdoe@school.edu'},
    ],
}


def _ok(record):
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = [record]
    return (resp, None)


class AltCredentialLookupTests(SimpleTestCase):
    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_returns_full_parsed_dict(self, mock_api, _accept):
        mock_api.return_value = _ok(RECORD)
        out = Ethos().lookup_person_by_alternative_credential('VAL', 'TYPE-ID')
        self.assertEqual(out, {
            'id': 'guid-1',
            'bannerid': 'B123',
            'username': 'jdoe',
            'other_email': 'jdoe@home.com',
            'raw': RECORD,
        })

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_sends_alternative_credentials_criteria(self, mock_api, _accept):
        mock_api.return_value = _ok(RECORD)
        Ethos().lookup_person_by_alternative_credential('VAL', 'TYPE-ID')
        url = mock_api.call_args.args[1]
        self.assertIn('alternativeCredentials', url)
        self.assertIn('TYPE-ID', url)
        self.assertIn('VAL', url)

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_not_ok_returns_none(self, mock_api, _accept):
        resp = MagicMock()
        resp.ok = False
        mock_api.return_value = (resp, None)
        self.assertIsNone(Ethos().lookup_person_by_alternative_credential('V', 'T'))

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_empty_list_returns_none(self, mock_api, _accept):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = []
        mock_api.return_value = (resp, None)
        self.assertIsNone(Ethos().lookup_person_by_alternative_credential('V', 'T'))


class BannerIdLookupTests(SimpleTestCase):
    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_returns_full_parsed_dict(self, mock_api, _accept):
        mock_api.return_value = _ok(RECORD)
        out = Ethos().lookup_person_by_banner_id('B123')
        self.assertEqual(out, {
            'id': 'guid-1',
            'username': 'jdoe',
            'school_email': 'jdoe@school.edu',
            'raw': RECORD,
        })

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_sends_bannerid_credentials_criteria(self, mock_api, _accept):
        mock_api.return_value = _ok(RECORD)
        Ethos().lookup_person_by_banner_id('B123')
        url = mock_api.call_args.args[1]
        self.assertIn('bannerId', url)
        self.assertIn('B123', url)

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    @patch.object(Ethos, '_api_request')
    def test_not_ok_returns_none(self, mock_api, _accept):
        resp = MagicMock()
        resp.ok = False
        mock_api.return_value = (resp, None)
        self.assertIsNone(Ethos().lookup_person_by_banner_id('B123'))

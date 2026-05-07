from unittest.mock import patch, MagicMock

from django.test import TestCase

from ethos.ethos.library.ethos import Ethos


class LookupPersonByBannerIdTests(TestCase):
    def _mock_response(self, ok=True, body=None):
        resp = MagicMock()
        resp.ok = ok
        resp.json.return_value = body if body is not None else []
        return resp

    def test_returns_none_on_non_ok(self):
        eth = Ethos.__new__(Ethos)
        with patch.object(eth, '_api_request') as api:
            api.return_value = (self._mock_response(ok=False), MagicMock())
            self.assertIsNone(eth.lookup_person_by_banner_id('01070122'))

    def test_returns_none_on_empty_list(self):
        eth = Ethos.__new__(Ethos)
        with patch.object(eth, '_api_request') as api:
            api.return_value = (self._mock_response(ok=True, body=[]), MagicMock())
            self.assertIsNone(eth.lookup_person_by_banner_id('01070122'))

    def test_extracts_id_username_and_school_email(self):
        record = {
            'id': '35f28a64-3842-452d-bc2b-6e2b457a2c1a',
            'credentials': [
                {'type': 'bannerSourcedId', 'value': '1022611'},
                {'type': 'bannerUserName', 'value': 'jburdick7'},
                {'type': 'bannerId', 'value': '01070122'},
            ],
            'emails': [
                {'address': '14097@adnaschools.org',
                 'type': {'emailType': 'personal'}},
                {'address': 'jburdick7@ewu.edu',
                 'preference': 'primary',
                 'type': {'emailType': 'school'}},
            ],
        }
        eth = Ethos.__new__(Ethos)
        with patch.object(eth, '_api_request') as api, \
             patch.object(eth, 'get_preferred_accept_header', return_value='application/json'):
            api.return_value = (self._mock_response(ok=True, body=[record]), MagicMock())
            result = eth.lookup_person_by_banner_id('01070122')

        self.assertEqual(result['id'], '35f28a64-3842-452d-bc2b-6e2b457a2c1a')
        self.assertEqual(result['username'], 'jburdick7')
        self.assertEqual(result['school_email'], 'jburdick7@ewu.edu')
        self.assertEqual(result['raw'], record)

    def test_school_email_none_when_only_personal_present(self):
        record = {
            'id': 'abc',
            'credentials': [{'type': 'bannerUserName', 'value': 'foo'}],
            'emails': [
                {'address': 'foo@example.com', 'type': {'emailType': 'personal'}},
            ],
        }
        eth = Ethos.__new__(Ethos)
        with patch.object(eth, '_api_request') as api, \
             patch.object(eth, 'get_preferred_accept_header', return_value='application/json'):
            api.return_value = (self._mock_response(ok=True, body=[record]), MagicMock())
            result = eth.lookup_person_by_banner_id('01070122')

        self.assertIsNone(result['school_email'])

    def test_url_uses_credentials_criteria(self):
        eth = Ethos.__new__(Ethos)
        captured = {}
        def fake_api_request(method, url, message_type, **kwargs):
            captured['url'] = url
            captured['message_type'] = message_type
            return self._mock_response(ok=False), MagicMock()

        with patch.object(eth, '_api_request', side_effect=fake_api_request), \
             patch.object(eth, 'get_preferred_accept_header', return_value='application/json'):
            eth.lookup_person_by_banner_id('01070122')

        self.assertIn('criteria=', captured['url'])
        self.assertIn('bannerId', captured['url'])
        self.assertIn('01070122', captured['url'])
        self.assertEqual(captured['message_type'], 'lookup_person_by_banner_id')

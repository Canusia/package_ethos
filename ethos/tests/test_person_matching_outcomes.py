import importlib.util
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
else:
    from ethos.library.ethos import Ethos


def _ok(body):
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = body
    return resp


@override_settings(MULTI_CAMPUS=False)
@patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
@patch.object(Ethos, 'studentJSON', return_value='{}')
@patch.object(Ethos, '_api_request')
class GetOrCreatePersonOutcomesTests(SimpleTestCase):
    """package_ethos#9: a 2xx with no outcomes must not lose the request id / person GUID."""

    def test_missing_outcomes_keeps_ids(self, mock_api, _json, _accept):
        mock_api.return_value = (_ok({'id': 'req-1', 'person': {'id': 'p-1'}}), 'log')
        self.assertEqual(Ethos().get_or_create_person(object()), ('req-1', 'p-1', None, 'log'))

    def test_empty_outcomes_keeps_ids(self, mock_api, _json, _accept):
        mock_api.return_value = (_ok({'id': 'req-1', 'person': {'id': 'p-1'}, 'outcomes': []}), 'log')
        self.assertEqual(Ethos().get_or_create_person(object()), ('req-1', 'p-1', None, 'log'))

    def test_null_outcomes_and_person(self, mock_api, _json, _accept):
        mock_api.return_value = (_ok({'id': 'req-1', 'person': None, 'outcomes': None}), 'log')
        self.assertEqual(Ethos().get_or_create_person(object()), ('req-1', None, None, 'log'))

    def test_first_outcome_status(self, mock_api, _json, _accept):
        mock_api.return_value = (_ok({'id': 'req-1', 'person': {'id': 'p-1'},
                                      'outcomes': [{'status': 'matched'}]}), 'log')
        self.assertEqual(Ethos().get_or_create_person(object())[2], 'matched')


@override_settings(MULTI_CAMPUS=False)
@patch.object(Ethos, '_api_request')
class GetRequestStatusTests(SimpleTestCase):
    """package_ethos#8: no forced verbose, routed through _api_request, empty outcomes safe."""

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    def test_routes_through_api_request_with_default_accept(self, _accept, mock_api):
        mock_api.return_value = (_ok({'person': {'id': 'p-1'}, 'outcomes': [{'status': 'matched'}]}), 'log')

        self.assertEqual(Ethos().get_request_status('req-1'), ('p-1', 'matched', 'log'))

        args, kwargs = mock_api.call_args
        self.assertEqual(args[0], 'GET')
        self.assertTrue(args[1].endswith('/api/person-matching-requests/req-1'))
        self.assertEqual(args[2], 'person_request_status')
        self.assertTrue(kwargs.get('description'))
        self.assertEqual(kwargs['headers']['Accept'], 'application/vnd.hedtech.integration.v1+json')

    @patch.object(Ethos, 'get_preferred_accept_header', return_value='application/vnd.hedtech.integration.v2+json')
    def test_uses_preferred_accept(self, accept, mock_api):
        mock_api.return_value = (_ok({}), 'log')
        Ethos().get_request_status('req-1')
        accept.assert_called_with('person-matching-requests')
        self.assertEqual(mock_api.call_args.kwargs['headers']['Accept'],
                         'application/vnd.hedtech.integration.v2+json')

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    def test_not_verbose_by_default(self, _accept, mock_api):
        mock_api.return_value = (_ok({'person': {'id': 'p-1'}, 'outcomes': []}), 'log')
        with patch('builtins.print') as mock_print:
            Ethos().get_request_status('req-1')
        mock_print.assert_not_called()
        self.assertFalse(mock_api.call_args.kwargs.get('verbose', False))

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    def test_empty_outcomes(self, _accept, mock_api):
        mock_api.return_value = (_ok({'person': {'id': 'p-1'}, 'outcomes': []}), 'log')
        self.assertEqual(Ethos().get_request_status('req-1'), ('p-1', None, 'log'))

    @patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
    def test_not_ok(self, _accept, mock_api):
        resp = MagicMock()
        resp.ok = False
        mock_api.return_value = (resp, 'log')
        self.assertEqual(Ethos().get_request_status('req-1'), (None, None, 'log'))

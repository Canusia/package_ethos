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

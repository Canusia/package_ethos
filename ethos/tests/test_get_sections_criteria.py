import importlib.util
import json
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase, override_settings

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
else:
    from ethos.library.ethos import Ethos

PERIOD = 'e13629a1-11ad-4794-bc78-ada5fa5e0269'
MAXIMUM = 'application/vnd.hedtech.integration.sections-maximum.v16+json'


def _resp(records):
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = records
    resp.headers = {'x-total-count': str(len(records))}
    return (resp, None)


def _criteria(call):
    return json.loads(parse_qs(urlparse(call.args[1]).query)['criteria'][0])


@override_settings(MULTI_CAMPUS=False)
@patch.object(Ethos, 'get_preferred_accept_header', return_value=None)
@patch.object(Ethos, '_api_request')
class GetSectionsReportingPeriodFallbackTests(SimpleTestCase):
    """Some Banner instances (Lamar LSCPA) tie sections to the term only through
    reportingAcademicPeriod; academicPeriod.detail returns [] for them."""

    def test_uses_academic_period_detail_when_it_returns_sections(self, mock_api, _accept):
        mock_api.return_value = _resp([{'id': 's1'}])
        out = Ethos().get_sections(period_id=PERIOD)
        self.assertEqual(out, [{'id': 's1'}])
        self.assertEqual(mock_api.call_count, 1)
        self.assertEqual(_criteria(mock_api.call_args), {'academicPeriod': {'detail': {'id': PERIOD}}})

    def test_falls_back_to_reporting_academic_period_when_empty(self, mock_api, _accept):
        mock_api.side_effect = [_resp([]), _resp([{'id': 's1'}, {'id': 's2'}])]
        out = Ethos().get_sections(period_id=PERIOD)
        self.assertEqual(out, [{'id': 's1'}, {'id': 's2'}])
        self.assertEqual(_criteria(mock_api.call_args_list[1]), {'reportingAcademicPeriod': {'id': PERIOD}})

    def test_no_fallback_when_criteria_is_explicit(self, mock_api, _accept):
        mock_api.return_value = _resp([])
        out = Ethos().get_sections(period_id=PERIOD, criteria={'code': 'X'})
        self.assertEqual(out, [])
        self.assertEqual(mock_api.call_count, 1)

    def test_no_fallback_for_non_maximum_representation(self, mock_api, _accept):
        mock_api.return_value = _resp([])
        Ethos().get_sections(period_id=PERIOD, accept='application/vnd.hedtech.integration.v16+json')
        self.assertEqual(mock_api.call_count, 1)

    def test_fallback_on_maximum_default_accept(self, mock_api, _accept):
        mock_api.side_effect = [_resp([]), _resp([])]
        self.assertEqual(Ethos().get_sections(period_id=PERIOD, accept=MAXIMUM), [])
        self.assertEqual(mock_api.call_count, 2)

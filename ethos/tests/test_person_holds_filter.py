import importlib.util
from unittest.mock import patch

from django.test import SimpleTestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
else:
    from ethos.library.ethos import Ethos

HOLDS = [
    {'id': 'h1', 'restrictionCode': 'RSCH'},
    {'id': 'h2', 'restrictionCode': 'FINA'},
    {'id': 'h3', 'restrictionCode': 'RSCH'},
    {'id': 'h4'},  # no restrictionCode
]


class FilteredPersonHoldsTests(SimpleTestCase):
    @patch.object(Ethos, '_load_sis_guids',
                  return_value={'hold_restriction_codes': ['RSCH']})
    @patch.object(Ethos, 'get_person_holds')
    def test_filters_to_configured_codes(self, mock_holds, _guids):
        mock_holds.return_value = HOLDS
        out = Ethos().get_filtered_person_holds('P1')
        self.assertEqual([h['id'] for h in out], ['h1', 'h3'])
        mock_holds.assert_called_once_with('P1')

    @patch.object(Ethos, '_load_sis_guids', return_value={})
    @patch.object(Ethos, 'get_person_holds')
    def test_no_codes_configured_returns_all(self, mock_holds, _guids):
        mock_holds.return_value = HOLDS
        self.assertEqual(Ethos().get_filtered_person_holds('P1'), HOLDS)

    @patch.object(Ethos, '_load_sis_guids',
                  return_value={'hold_restriction_codes': []})
    @patch.object(Ethos, 'get_person_holds')
    def test_empty_codes_list_returns_all(self, mock_holds, _guids):
        mock_holds.return_value = HOLDS
        self.assertEqual(Ethos().get_filtered_person_holds('P1'), HOLDS)

    @patch.object(Ethos, '_load_sis_guids',
                  return_value={'hold_restriction_codes': ['XXXX']})
    @patch.object(Ethos, 'get_person_holds')
    def test_no_match_returns_empty(self, mock_holds, _guids):
        mock_holds.return_value = HOLDS
        self.assertEqual(Ethos().get_filtered_person_holds('P1'), [])

    @patch.object(Ethos, '_load_sis_guids',
                  return_value={'hold_restriction_codes': ['RSCH']})
    @patch.object(Ethos, 'get_person_holds')
    def test_codes_are_trimmed_and_exact(self, mock_holds, _guids):
        mock_holds.return_value = [{'id': 'a', 'restrictionCode': ' RSCH '},
                                   {'id': 'b', 'restrictionCode': 'RSCHX'}]
        out = Ethos().get_filtered_person_holds('P1')
        self.assertEqual([h['id'] for h in out], ['a'])   # trimmed match; no partial

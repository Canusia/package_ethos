from unittest.mock import patch, MagicMock

from django.test import TestCase

try:
    from ethos.ethos.library.registration import RegistrationMixin
except ImportError:
    from ethos.library.registration import RegistrationMixin


STUDENT_ID = '35f28a64-3842-452d-bc2b-6e2b457a2c1a'
PERIOD_ID = 'c0496632-88d2-4fac-95e6-d44234c99ed5'
INELIGIBLE_STUDENT_ID = 'fb76fbb6-249f-4b93-8ee8-40633f1b75bc'

ELIGIBLE_RECORD = {
    'academicPeriod': {'id': PERIOD_ID},
    'alternatePin': 'notRequired',
    'eligibilityStatus': 'eligible',
    'endOn': '2026-12-04',
    'startOn': '2026-04-21',
    'student': {'id': STUDENT_ID},
}

INELIGIBLE_RECORD = {
    'academicPeriod': {'id': PERIOD_ID},
    'alternatePin': 'notRequired',
    'eligibilityStatus': 'ineligible',
    'endOn': '2026-12-04',
    'ineligibilityReasons': [
        'You must be a student for the term.',
        'Time tickets prevent registration at this time.',
        'You require re-admission prior to registration.',
    ],
    'startOn': '2026-04-21',
    'student': {'id': INELIGIBLE_STUDENT_ID},
}


def mock_response(data, status_code=200):
    """Build a mock response object matching the ethos test convention."""
    resp = MagicMock()
    resp.ok = status_code == 200
    resp.status_code = status_code
    resp.text = str(data)
    resp.json.return_value = data
    return resp


def mock_sis_log():
    return MagicMock()


class RegistrationEligibilityTest(TestCase):
    """Tests for RegistrationMixin.get_registration_eligibility."""

    def setUp(self):
        self.mixin = RegistrationMixin.__new__(RegistrationMixin)
        self.mixin.URL = 'https://integrate.elluciancloud.com'
        self.mixin._cached_token = 'fake-token'
        self.mixin._token_expires_at = 9999999999

    @patch.object(RegistrationMixin, 'get_preferred_accept_header', return_value=None)
    @patch.object(RegistrationMixin, '_api_request')
    def test_eligible_returns_normalized_dict(self, mock_req, _mock_accept):
        mock_req.return_value = (mock_response([ELIGIBLE_RECORD]), mock_sis_log())

        result = self.mixin.get_registration_eligibility(STUDENT_ID, PERIOD_ID)

        self.assertEqual(result, {
            'eligibility_status': 'eligible',
            'alternate_pin': 'notRequired',
            'start_on': '2026-04-21',
            'end_on': '2026-12-04',
            'ineligibility_reasons': [],
        })

    @patch.object(RegistrationMixin, 'get_preferred_accept_header', return_value=None)
    @patch.object(RegistrationMixin, '_api_request')
    def test_ineligible_includes_reasons(self, mock_req, _mock_accept):
        mock_req.return_value = (mock_response([INELIGIBLE_RECORD]), mock_sis_log())

        result = self.mixin.get_registration_eligibility(INELIGIBLE_STUDENT_ID, PERIOD_ID)

        self.assertEqual(result['eligibility_status'], 'ineligible')
        self.assertEqual(len(result['ineligibility_reasons']), 3)
        self.assertIn('You must be a student for the term.', result['ineligibility_reasons'])

    @patch.object(RegistrationMixin, 'get_preferred_accept_header', return_value=None)
    @patch.object(RegistrationMixin, '_api_request')
    def test_criteria_url_targets_endpoint_with_both_ids(self, mock_req, _mock_accept):
        mock_req.return_value = (mock_response([ELIGIBLE_RECORD]), mock_sis_log())

        self.mixin.get_registration_eligibility(STUDENT_ID, PERIOD_ID)

        url = mock_req.call_args[0][1]
        self.assertIn('/api/student-registration-eligibilities', url)
        self.assertIn('criteria', url)
        self.assertIn(STUDENT_ID, url)
        self.assertIn(PERIOD_ID, url)
        self.assertIn('academicPeriod', url)

    @patch.object(RegistrationMixin, 'get_preferred_accept_header', return_value=None)
    @patch.object(RegistrationMixin, '_api_request')
    def test_empty_list_returns_none(self, mock_req, _mock_accept):
        mock_req.return_value = (mock_response([]), mock_sis_log())

        result = self.mixin.get_registration_eligibility(STUDENT_ID, PERIOD_ID)

        self.assertIsNone(result)

    @patch.object(RegistrationMixin, 'get_preferred_accept_header', return_value=None)
    @patch.object(RegistrationMixin, '_api_request')
    def test_api_error_returns_none(self, mock_req, _mock_accept):
        mock_req.return_value = (mock_response({'error': 'bad'}, status_code=400), mock_sis_log())

        result = self.mixin.get_registration_eligibility(STUDENT_ID, PERIOD_ID)

        self.assertIsNone(result)

    @patch.object(RegistrationMixin, 'get_preferred_accept_header',
                  return_value='application/vnd.hedtech.integration.v6+json')
    @patch.object(RegistrationMixin, '_api_request')
    def test_uses_preferred_accept_header_when_configured(self, mock_req, _mock_accept):
        mock_req.return_value = (mock_response([ELIGIBLE_RECORD]), mock_sis_log())

        self.mixin.get_registration_eligibility(STUDENT_ID, PERIOD_ID)

        sent_headers = mock_req.call_args.kwargs['headers']
        self.assertEqual(sent_headers['Accept'], 'application/vnd.hedtech.integration.v6+json')

"""create_section_registration: (success, log) contract over all 3 Ethos shapes.

All network is mocked at ethos.ethos.library.registration.requests.post —
no real API calls. Success is HTTP-ok AND no top-level 'errors' array.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase

try:
    from ethos.ethos.library.ethos import Ethos
    from ethos.ethos.models import EthosLog
except ImportError:
    from ethos.library.ethos import Ethos
    from ethos.models import EthosLog


SUCCESS_BODY = {
    "registrant": {"id": "4f35bbd5-aaaa-bbbb-cccc-000000000001"},
    "section": {"id": "20061ab5-aaaa-bbbb-cccc-000000000002"},
    "academicLevel": {"id": "d8397846-aaaa-bbbb-cccc-000000000003"},
    "originallyRegisteredOn": "2026-06-04",
    "status": {
        "registrationStatus": "registered",
        "sectionRegistrationStatusReason": "registered",
        "detail": {"id": "ff507eda-aaaa-bbbb-cccc-000000000004"},
    },
    "statusDate": "2026-06-04",
    "credit": {"measure": "credit", "registrationCredit": 3.0},
    "id": "184fa990-96fa-4166-8405-37629b1c2ad5",
}

PREREQ_ERROR_BODY = {
    "errors": [{
        "code": "sectionRegistrations",
        "description": "Unknown error code.",
        "message": ("CH-001A-3308 - The following required prerequisite for "
                    "course CH-001A is not started. CH 003 or one year high "
                    "school chemistry"),
    }]
}

LOCKED_ERROR_BODY = {
    "errors": [{
        "code": "sectionRegistrations",
        "description": "Unknown error code.",
        "message": "PERSON.ST record with ID '0715184' is locked.",
    }]
}


class CreateSectionRegistrationTests(TestCase):

    def setUp(self):
        self.ethos = Ethos()
        p = patch.object(self.ethos, 'get_auth_token', return_value='fake')
        p.start()
        self.addCleanup(p.stop)

    def _resp(self, ok, status, body):
        import json
        resp = MagicMock()
        resp.ok = ok
        resp.status_code = status
        resp.json.return_value = body
        resp.text = json.dumps(body)
        return resp

    @patch('ethos.ethos.library.registration.requests.post')
    def test_success_returns_true_and_log_with_guid(self, mock_post):
        mock_post.return_value = self._resp(True, 200, SUCCESS_BODY)
        success, log = self.ethos.create_section_registration(
            registrant_sis_id='4f35bbd5-aaaa-bbbb-cccc-000000000001',
            section_sis_id='20061ab5-aaaa-bbbb-cccc-000000000002',
        )
        self.assertTrue(success)
        self.assertIsInstance(log, EthosLog)
        self.assertEqual(log.response_json.get('id'),
                         '184fa990-96fa-4166-8405-37629b1c2ad5')

    @patch('ethos.ethos.library.registration.requests.post')
    def test_errors_array_with_http_200_is_failure(self, mock_post):
        # Ethos sometimes returns 200 with an errors array; must be False.
        mock_post.return_value = self._resp(True, 200, PREREQ_ERROR_BODY)
        success, log = self.ethos.create_section_registration(
            registrant_sis_id='S1', section_sis_id='SEC1',
        )
        self.assertFalse(success)
        self.assertIn('prerequisite', log.response_json['errors'][0]['message'])

    @patch('ethos.ethos.library.registration.requests.post')
    def test_prereq_error_returns_false_and_message(self, mock_post):
        mock_post.return_value = self._resp(False, 400, PREREQ_ERROR_BODY)
        success, log = self.ethos.create_section_registration(
            registrant_sis_id='S1', section_sis_id='SEC1',
        )
        self.assertFalse(success)
        self.assertEqual(
            log.response_json['errors'][0]['message'],
            ('CH-001A-3308 - The following required prerequisite for course '
             'CH-001A is not started. CH 003 or one year high school chemistry'),
        )

    @patch('ethos.ethos.library.registration.requests.post')
    def test_locked_record_error_returns_false_and_message(self, mock_post):
        mock_post.return_value = self._resp(False, 400, LOCKED_ERROR_BODY)
        success, log = self.ethos.create_section_registration(
            registrant_sis_id='S1', section_sis_id='SEC1',
        )
        self.assertFalse(success)
        self.assertEqual(
            log.response_json['errors'][0]['message'],
            "PERSON.ST record with ID '0715184' is locked.",
        )

    @patch('ethos.ethos.library.registration.requests.post')
    def test_posts_to_section_registrations_with_registrant_and_section(self, mock_post):
        mock_post.return_value = self._resp(True, 200, SUCCESS_BODY)
        self.ethos.create_section_registration(
            registrant_sis_id='REG-GUID', section_sis_id='SEC-GUID',
        )
        args, kwargs = mock_post.call_args
        url = args[0] if args else kwargs.get('url')
        self.assertTrue(url.endswith('/api/section-registrations'))
        body = kwargs['json']
        self.assertEqual(body['registrant']['id'], 'REG-GUID')
        self.assertEqual(body['section']['id'], 'SEC-GUID')
        self.assertEqual(body['status']['registrationStatus'], 'registered')

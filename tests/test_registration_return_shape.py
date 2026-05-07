"""Pin the (success, log) return shape of RegistrationMixin methods."""

from unittest.mock import patch, MagicMock
from django.test import TestCase

try:
    from ethos.ethos.library.ethos import Ethos
    from ethos.ethos.models import EthosLog
except ImportError:
    from ethos.library.ethos import Ethos
    from ethos.models import EthosLog


class MirrorRegistrationReturnShapeTests(TestCase):

    def setUp(self):
        self.ethos = Ethos()
        patcher = patch.object(self.ethos, 'get_auth_token', return_value='fake')
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fake_response(self, ok=True, status=200, body=None, text=None):
        resp = MagicMock()
        resp.ok = ok
        resp.status_code = status
        body = body or {
            'id': '00000000-0000-0000-0000-000000000001',
            'status': {'registrationStatus': 'registered'},
        }
        resp.json.return_value = body
        resp.text = text if text is not None else '{"id": "00000000-0000-0000-0000-000000000001"}'
        return resp

    @patch('ethos.ethos.library.registration.requests.post')
    def test_mirror_registration_create_returns_two_tuple(self, mock_post):
        mock_post.return_value = self._fake_response(ok=True)
        result = self.ethos.mirror_registration(
            student_sis_id='S1', section_id='SEC1',
            status='registered', registration_id=None,
        )
        self.assertEqual(len(result), 2,
                         f'expected (success, log); got {len(result)}-tuple')
        success, log = result
        self.assertTrue(success)
        self.assertIsInstance(log, EthosLog)

    @patch('ethos.ethos.library.registration.requests.put')
    def test_mirror_registration_update_returns_two_tuple(self, mock_put):
        mock_put.return_value = self._fake_response(ok=True)
        result = self.ethos.mirror_registration(
            student_sis_id='S1', section_id='SEC1',
            status='dropped', registration_id='REG1',
        )
        self.assertEqual(len(result), 2)
        success, log = result
        self.assertTrue(success)
        self.assertIsInstance(log, EthosLog)

    @patch('ethos.ethos.library.registration.requests.post')
    def test_mirror_linked_registrations_returns_two_tuple(self, mock_post):
        mock_post.return_value = self._fake_response(
            ok=True, body={'registrations': [{'statusIndicator': 'S'}]}
        )
        result = self.ethos.mirror_linked_registrations(
            student_banner_id='B1', term_code='202620', crns=['12345']
        )
        self.assertEqual(len(result), 2)
        success, log = result
        self.assertTrue(success)
        self.assertIsInstance(log, EthosLog)

    @patch('ethos.ethos.library.registration.requests.post')
    def test_mirror_registration_failure_returns_log_with_error(self, mock_post):
        mock_post.return_value = self._fake_response(
            ok=False, status=400,
            body={'errors': [{'message': 'bad student'}]},
            text='{"errors":[{"message":"bad student"}]}',
        )
        success, log = self.ethos.mirror_registration(
            student_sis_id='S1', section_id='SEC1',
            status='registered', registration_id=None,
        )
        self.assertFalse(success)
        self.assertIsInstance(log, EthosLog)
        self.assertEqual(log.response_status, 400)
        self.assertIn('bad student', log.response_body)

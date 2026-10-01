"""GradesMixin student-unverified-grades calls (Banner final-grade submission)."""
import json
from unittest.mock import MagicMock, patch

from django.test import TestCase

try:
    from ethos.ethos.library.ethos import Ethos
    from ethos.ethos.models import EthosLog
except ImportError:
    from ethos.library.ethos import Ethos
    from ethos.models import EthosLog

REG = 'b1132b12-cda9-4e2a-bc48-a06870e41802'
GRADE = '1a2387cf-eb76-4dfb-b53d-6457068f5b15'
TYPE = 'f70332ec-52b3-461b-808f-903ad1aa1883'
BY = '1a156b56-391b-41fa-b309-336d19392109'
RECORD = '3b300cc1-bcf1-496a-a0a1-d451bd52be42'
SUBMISSION_CT = 'application/vnd.hedtech.integration.student-unverified-grades-submissions.v1+json'


def _resp(ok=True, status=200, body=None):
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status
    resp.json.return_value = body if body is not None else {'id': RECORD}
    resp.text = json.dumps(body if body is not None else {'id': RECORD})
    return resp


class SubmitUnverifiedGradeTests(TestCase):
    def setUp(self):
        self.ethos = Ethos()
        patcher = patch.object(self.ethos, 'get_auth_token', return_value='fake')
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch('ethos.ethos.library.base.requests.post')
    def test_create_posts_nil_guid_with_submission_content_type(self, mock_post):
        mock_post.return_value = _resp(status=201)

        success, log = self.ethos.submit_unverified_grade(REG, GRADE, TYPE, submitted_by_id=BY)

        self.assertTrue(success)
        self.assertIsInstance(log, EthosLog)
        url = mock_post.call_args.args[0]
        self.assertTrue(url.endswith('/api/student-unverified-grades'))
        headers = mock_post.call_args.kwargs['headers']
        self.assertEqual(headers['Content-Type'], SUBMISSION_CT)
        self.assertEqual(headers['Accept'], 'application/vnd.hedtech.integration.v1+json')
        body = json.loads(mock_post.call_args.kwargs['data'])
        self.assertEqual(body, {
            'id': '00000000-0000-0000-0000-000000000000',
            'sectionRegistration': {'id': REG},
            'grade': {'type': {'id': TYPE}, 'grade': {'id': GRADE}},
            'submittedBy': {'id': BY},
        })

    @patch('ethos.ethos.library.base.requests.post')
    def test_submitted_by_omitted_when_not_given(self, mock_post):
        mock_post.return_value = _resp(status=201)

        self.ethos.submit_unverified_grade(REG, GRADE, TYPE)

        body = json.loads(mock_post.call_args.kwargs['data'])
        self.assertNotIn('submittedBy', body)

    @patch('ethos.ethos.library.base.requests.put')
    def test_update_puts_to_record_url_with_record_id(self, mock_put):
        mock_put.return_value = _resp()

        success, _ = self.ethos.submit_unverified_grade(REG, GRADE, TYPE, record_id=RECORD)

        self.assertTrue(success)
        self.assertTrue(mock_put.call_args.args[0].endswith(f'/api/student-unverified-grades/{RECORD}'))
        body = json.loads(mock_put.call_args.kwargs['data'])
        self.assertEqual(body['id'], RECORD)

    @patch('ethos.ethos.library.base.requests.post')
    def test_failure_returns_false_and_logged_response(self, mock_post):
        mock_post.return_value = _resp(ok=False, status=400,
                                       body={'errors': [{'message': 'Section is not gradable'}]})

        success, log = self.ethos.submit_unverified_grade(REG, GRADE, TYPE)

        self.assertFalse(success)
        self.assertEqual(log.response_status, 400)


class GetUnverifiedGradesTests(TestCase):
    def setUp(self):
        self.ethos = Ethos()
        patcher = patch.object(self.ethos, 'get_auth_token', return_value='fake')
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch('ethos.ethos.library.base.requests.get')
    def test_filters_by_section_registration(self, mock_get):
        mock_get.return_value = _resp(body=[{'id': RECORD}])

        rows = self.ethos.get_unverified_grades(REG)

        self.assertEqual(rows, [{'id': RECORD}])
        self.assertIn('sectionRegistration', mock_get.call_args.args[0])
        self.assertIn(REG, mock_get.call_args.args[0])

    @patch('ethos.ethos.library.base.requests.get')
    def test_error_returns_empty_list(self, mock_get):
        mock_get.return_value = _resp(ok=False, status=500, body={})

        self.assertEqual(self.ethos.get_unverified_grades(REG), [])

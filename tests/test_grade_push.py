"""ethos.grade_push.push_final_grade — registration -> Banner unverified grade."""
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
from django.test import TestCase

try:
    from ethos.ethos import grade_push
    from ethos.ethos.library.ethos import Ethos
    from ethos.ethos.library.grades import UnverifiedGradesLookupError
except ImportError:
    from ethos import grade_push
    from ethos.library.ethos import Ethos
    from ethos.library.grades import UnverifiedGradesLookupError

REG_SIS = 'b1132b12-cda9-4e2a-bc48-a06870e41802'
TYPE = 'f70332ec-52b3-461b-808f-903ad1aa1883'
A_GUID = '1a2387cf-eb76-4dfb-b53d-6457068f5b15'
BY = '1a156b56-391b-41fa-b309-336d19392109'
RECORD = '3b300cc1-bcf1-496a-a0a1-d451bd52be42'

GUIDS = {
    'final_grade_type': {'id': TYPE},
    'grade_map': {'A': A_GUID},
    'grade_submitted_by': {'id': BY},
}


def _log(ok=True, body=None, status=201, error=''):
    log = MagicMock()
    log.pk = 7
    log.response_json = body if body is not None else {'id': RECORD}
    log.response_status = status
    log.error_message = error
    return log


class PushFinalGradeTests(TestCase):
    def setUp(self):
        # Reset the module-level client cache so this test's mocked Ethos()
        # is what _get_client() actually returns, rather than a client
        # cached by some earlier test.
        grade_push._client = None
        self.addCleanup(setattr, grade_push, '_client', None)

        self.ethos = MagicMock()
        self.ethos._load_sis_guids.return_value = dict(GUIDS)
        self.ethos.get_unverified_grades.return_value = []
        self.ethos.submit_unverified_grade.return_value = (True, _log())
        patcher = patch.object(grade_push, 'Ethos', return_value=self.ethos)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.registration = SimpleNamespace(sis_id=REG_SIS)

    def test_creates_when_banner_has_no_record(self):
        result = grade_push.push_final_grade(self.registration, 'A')

        self.assertTrue(result.success)
        self.assertEqual(result.record_id, RECORD)
        self.ethos.submit_unverified_grade.assert_called_once_with(
            REG_SIS, A_GUID, TYPE, submitted_by_id=BY, record_id=None)

    def test_existing_banner_record_is_updated(self):
        self.ethos.get_unverified_grades.return_value = [{'id': RECORD}]

        grade_push.push_final_grade(self.registration, 'A')

        self.assertEqual(
            self.ethos.submit_unverified_grade.call_args.kwargs['record_id'], RECORD)

    def test_known_record_id_skips_lookup(self):
        grade_push.push_final_grade(self.registration, 'A', existing_record_id=RECORD)

        self.ethos.get_unverified_grades.assert_not_called()
        self.assertEqual(
            self.ethos.submit_unverified_grade.call_args.kwargs['record_id'], RECORD)

    def test_lookup_failure_fails_without_post(self):
        """A failed existing-record lookup is not "no record": it must fail
        the row with a clear reason, and never fall through to POST (which
        would create a duplicate instead of updating the record that may
        well already exist in Banner)."""
        self.ethos.get_unverified_grades.side_effect = UnverifiedGradesLookupError(500)

        result = grade_push.push_final_grade(self.registration, 'A')

        self.assertFalse(result.success)
        self.assertIn('Could not check for an existing Banner record', result.error)
        self.assertIn('500', result.error)
        self.ethos.submit_unverified_grade.assert_not_called()

    def test_submitted_by_none_when_not_configured(self):
        guids = dict(GUIDS)
        guids.pop('grade_submitted_by')
        self.ethos._load_sis_guids.return_value = guids

        grade_push.push_final_grade(self.registration, 'A')

        self.assertIsNone(
            self.ethos.submit_unverified_grade.call_args.kwargs['submitted_by_id'])

    def test_unmapped_grade_fails_without_http(self):
        result = grade_push.push_final_grade(self.registration, 'B+')

        self.assertFalse(result.success)
        self.assertIn("'B+'", result.error)
        self.ethos.submit_unverified_grade.assert_not_called()
        self.ethos.get_unverified_grades.assert_not_called()

    def test_grade_key_is_stripped_but_case_sensitive(self):
        self.assertTrue(grade_push.push_final_grade(self.registration, ' A ').success)
        self.assertFalse(grade_push.push_final_grade(self.registration, 'a').success)

    def test_missing_sis_id_fails_without_http(self):
        result = grade_push.push_final_grade(SimpleNamespace(sis_id=None), 'A')

        self.assertFalse(result.success)
        self.assertIn('section-registration', result.error)
        self.ethos.submit_unverified_grade.assert_not_called()

    def test_missing_grade_type_fails_without_http(self):
        self.ethos._load_sis_guids.return_value = {'grade_map': {'A': A_GUID}}

        result = grade_push.push_final_grade(self.registration, 'A')

        self.assertFalse(result.success)
        self.assertIn('final_grade_type', result.error)
        self.ethos.submit_unverified_grade.assert_not_called()

    def test_banner_error_is_returned(self):
        self.ethos.submit_unverified_grade.return_value = (
            False, _log(status=400, body={}, error='Section is not gradable'))

        result = grade_push.push_final_grade(self.registration, 'A')

        self.assertFalse(result.success)
        self.assertEqual(result.error, 'Section is not gradable')
        self.assertTrue(result.log_url.endswith('/7/'))

    def test_unauthorized_401_names_authentication(self):
        self.ethos.submit_unverified_grade.return_value = (
            False, _log(status=401, body={}, error=''))

        result = grade_push.push_final_grade(self.registration, 'A')

        self.assertFalse(result.success)
        self.assertIn('authentic', result.error.lower())

    def test_forbidden_403_names_authentication(self):
        self.ethos.submit_unverified_grade.return_value = (
            False, _log(status=403, body={}, error='Forbidden'))

        result = grade_push.push_final_grade(self.registration, 'A')

        self.assertFalse(result.success)
        self.assertIn('authentic', result.error.lower())

    def test_config_errors_lists_each_problem(self):
        self.assertEqual(len(grade_push.config_errors({})), 2)
        self.assertEqual(grade_push.config_errors(GUIDS), [])


class ClientReuseTests(TestCase):
    """Two pushes in the same process must authenticate once: `push_final_grade`
    reuses one Ethos client (and its token cache) via `_get_client()`, rather
    than constructing a fresh `Ethos()` -- and re-authenticating -- per
    registration."""

    def setUp(self):
        grade_push._client = None
        self.addCleanup(setattr, grade_push, '_client', None)

    @patch('ethos.ethos.library.base.requests.put')
    @patch('ethos.ethos.library.base.requests.post')
    def test_two_pushes_authenticate_once(self, mock_post, mock_put):
        token = jwt.encode({'exp': time.time() + 3600}, 'secret', algorithm='HS256')
        mock_post.return_value = MagicMock(ok=True, text=token)

        put_resp = MagicMock(ok=True, status_code=200)
        put_resp.json.return_value = {'id': RECORD}
        put_resp.text = json.dumps({'id': RECORD})
        mock_put.return_value = put_resp

        registration = SimpleNamespace(sis_id=REG_SIS)
        with patch.object(Ethos, '_load_sis_guids', return_value=dict(GUIDS)):
            # existing_record_id is passed so both calls PUT directly,
            # skipping the GET lookup -- keeping this test to the one
            # question it's asking (auth call count), not Banner's read path.
            first = grade_push.push_final_grade(registration, 'A', existing_record_id=RECORD)
            second = grade_push.push_final_grade(registration, 'A', existing_record_id=RECORD)

        self.assertTrue(first.success)
        self.assertTrue(second.success)
        self.assertEqual(mock_post.call_count, 1, 'auth should only happen once')
        self.assertEqual(mock_put.call_count, 2)

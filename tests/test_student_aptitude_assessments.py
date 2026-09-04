"""Tests for StudentAptitudeAssessmentsMixin — student test scores.

Behaviour pinned here comes from the Ellucian OpenAPI spec for
student-aptitude-assessments v16.2.0 (Colleague / STUDENT.NON.COURSES).
"""

import datetime
import json
from unittest.mock import patch, MagicMock

from django.test import TestCase

try:
    from ethos.ethos.library.aptitude_assessments import AptitudeAssessmentsMixin
    from ethos.ethos.library.student_aptitude_assessments import (
        NIL_GUID, StudentAptitudeAssessmentsMixin)
except ImportError:
    from ethos.library.aptitude_assessments import AptitudeAssessmentsMixin
    from ethos.library.student_aptitude_assessments import (
        NIL_GUID, StudentAptitudeAssessmentsMixin)


STUDENT_GUID = '0f8f6277-62f9-4276-8c81-1ca13e940b92'
ACT_GUID = '7843496a-5cf4-45b0-9ba1-0b0a94188ee2'
SAT_GUID = 'b1f0e2d3-4c5b-6a79-8d0e-1f2a3b4c5d6e'
PCT_TYPE_1 = '1c9f60bb-97c6-4eb0-a744-8b760e20d5c4'
PCT_TYPE_2 = '2d0a71cc-a8d7-4fc1-b855-9c871f31e6d5'

ACT_SCORE = {
    'id': 'aaaa1111-2222-3333-4444-555566667777',
    'student': {'id': STUDENT_GUID},
    'assessment': {'id': ACT_GUID},
    'assessedOn': '2025-10-04',
    'score': {'type': 'numeric', 'value': 27},
    'status': 'active',
    'reported': 'official',
    'preference': 'primary',
    'percentiles': [{'value': 88, 'type': {'id': PCT_TYPE_1}}],
}

SAT_SCORE = {
    'id': 'bbbb1111-2222-3333-4444-555566667777',
    'student': {'id': STUDENT_GUID},
    'assessment': {'id': SAT_GUID},
    'assessedOn': '2025-05-02',
    'score': {'type': 'numeric', 'value': 640},
    # Colleague publishes the empty string where an enum has no value.
    'status': '',
    'reported': '',
    'preference': '',
}

CATALOG = [
    {'id': ACT_GUID, 'code': 'ACTC', 'title': 'ACT Composite'},
    {'id': SAT_GUID, 'code': 'SATM', 'title': 'SAT Mathematics'},
]


class Client(StudentAptitudeAssessmentsMixin, AptitudeAssessmentsMixin):
    """The two mixins as Ethos composes them."""


def mock_response(data, status_code=200, headers=None):
    resp = MagicMock()
    resp.ok = 200 <= status_code < 300
    resp.status_code = status_code
    resp.text = str(data)
    resp.json.return_value = data
    resp.headers = headers or {
        'x-total-count': str(len(data)) if isinstance(data, list) else '1',
        'x-max-page-size': '500',
    }
    return resp


def mock_sis_log():
    return MagicMock()


class StudentAptitudeAssessmentsReadTest(TestCase):

    def setUp(self):
        self.mixin = Client.__new__(Client)
        self.mixin.URL = 'https://integrate.elluciancloud.com'
        self.mixin._cached_token = 'fake-token'
        self.mixin._token_expires_at = 9999999999

    @patch.object(Client, '_api_request')
    def test_no_filters_sends_no_criteria(self, mock_req):
        mock_req.return_value = (mock_response([ACT_SCORE, SAT_SCORE]), mock_sis_log())

        result = self.mixin.get_student_aptitude_assessments()

        self.assertEqual(len(result), 2)
        self.assertNotIn('criteria', mock_req.call_args[0][1])

    @patch.object(Client, '_api_request')
    def test_filters_by_student(self, mock_req):
        mock_req.return_value = (mock_response([ACT_SCORE]), mock_sis_log())

        self.mixin.get_student_aptitude_assessments(student_id=STUDENT_GUID)

        url = mock_req.call_args[0][1]
        self.assertIn('criteria', url)
        self.assertIn(STUDENT_GUID, url)
        # the criteria carries only the student, not an assessment filter
        self.assertNotIn(ACT_GUID, url)

    @patch.object(Client, '_api_request')
    def test_filters_by_student_and_assessment_together(self, mock_req):
        mock_req.return_value = (mock_response([ACT_SCORE]), mock_sis_log())

        self.mixin.get_student_aptitude_assessments(
            student_id=STUDENT_GUID, assessment_id=ACT_GUID)

        url = mock_req.call_args[0][1]
        self.assertIn(STUDENT_GUID, url)
        self.assertIn(ACT_GUID, url)

    @patch.object(Client, '_api_request')
    def test_returns_empty_list_on_error(self, mock_req):
        mock_req.return_value = (mock_response({}, status_code=500), mock_sis_log())

        self.assertEqual(self.mixin.get_student_aptitude_assessments(), [])

    @patch.object(Client, '_api_request')
    def test_get_one_by_id(self, mock_req):
        mock_req.return_value = (mock_response(ACT_SCORE), mock_sis_log())

        result = self.mixin.get_student_aptitude_assessment(ACT_SCORE['id'])

        self.assertEqual(result['score']['value'], 27)
        self.assertIn(f"/api/student-aptitude-assessments/{ACT_SCORE['id']}",
                      mock_req.call_args[0][1])

    @patch.object(Client, '_api_request')
    def test_get_one_returns_none_when_missing(self, mock_req):
        mock_req.return_value = (mock_response({}, status_code=404), mock_sis_log())

        self.assertIsNone(self.mixin.get_student_aptitude_assessment('nope'))


class StudentScoresResolvedTest(TestCase):

    def setUp(self):
        self.mixin = Client.__new__(Client)
        self.mixin.URL = 'https://integrate.elluciancloud.com'
        self.mixin._cached_token = 'fake-token'
        self.mixin._token_expires_at = 9999999999

    def _route(self, scores):
        def side_effect(method, url, *a, **kw):
            if '/api/aptitude-assessments' in url:
                return mock_response(CATALOG), mock_sis_log()
            return mock_response(scores), mock_sis_log()
        return side_effect

    @patch.object(Client, '_api_request')
    def test_joins_assessment_title_onto_each_score(self, mock_req):
        mock_req.side_effect = self._route([ACT_SCORE, SAT_SCORE])

        rows = self.mixin.get_student_scores_resolved(STUDENT_GUID)

        self.assertEqual(rows[0]['assessment_title'], 'ACT Composite')
        self.assertEqual(rows[0]['assessment_code'], 'ACTC')
        self.assertEqual(rows[1]['assessment_title'], 'SAT Mathematics')

    @patch.object(Client, '_api_request')
    def test_flattens_the_numeric_score_value(self, mock_req):
        mock_req.side_effect = self._route([ACT_SCORE])

        rows = self.mixin.get_student_scores_resolved(STUDENT_GUID)

        self.assertEqual(rows[0]['score'], 27)
        self.assertEqual(rows[0]['score_type'], 'numeric')

    @patch.object(Client, '_api_request')
    def test_empty_string_enums_become_none(self, mock_req):
        mock_req.side_effect = self._route([SAT_SCORE])

        rows = self.mixin.get_student_scores_resolved(STUDENT_GUID)

        self.assertIsNone(rows[0]['status'])
        self.assertIsNone(rows[0]['reported'])
        self.assertIsNone(rows[0]['preference'])

    @patch.object(Client, '_api_request')
    def test_unknown_assessment_guid_still_yields_a_row(self, mock_req):
        orphan = dict(ACT_SCORE, assessment={'id': 'unknown-guid'})
        mock_req.side_effect = self._route([orphan])

        rows = self.mixin.get_student_scores_resolved(STUDENT_GUID)

        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['assessment_title'])
        self.assertEqual(rows[0]['assessment_id'], 'unknown-guid')

    @patch.object(Client, '_api_request')
    def test_keeps_the_raw_record(self, mock_req):
        mock_req.side_effect = self._route([ACT_SCORE])

        rows = self.mixin.get_student_scores_resolved(STUDENT_GUID)

        self.assertEqual(rows[0]['raw'], ACT_SCORE)


class StudentAptitudeAssessmentsWriteTest(TestCase):

    def setUp(self):
        self.mixin = Client.__new__(Client)
        self.mixin.URL = 'https://integrate.elluciancloud.com'
        self.mixin._cached_token = 'fake-token'
        self.mixin._token_expires_at = 9999999999

    def _sent_payload(self, mock_req):
        return json.loads(mock_req.call_args[1]['data'])

    # ── create ──

    @patch.object(Client, '_api_request')
    def test_create_posts_the_nil_guid_as_root_id(self, mock_req):
        mock_req.return_value = (mock_response(ACT_SCORE), mock_sis_log())

        self.mixin.create_student_aptitude_assessment(
            STUDENT_GUID, ACT_GUID, '2025-10-04', 27)

        self.assertEqual(self._sent_payload(mock_req)['id'], NIL_GUID)
        self.assertEqual(mock_req.call_args[0][0], 'POST')

    @patch.object(Client, '_api_request')
    def test_create_always_sends_a_numeric_score(self, mock_req):
        mock_req.return_value = (mock_response(ACT_SCORE), mock_sis_log())

        self.mixin.create_student_aptitude_assessment(
            STUDENT_GUID, ACT_GUID, '2025-10-04', '27')

        score = self._sent_payload(mock_req)['score']
        self.assertEqual(score, {'type': 'numeric', 'value': 27.0})

    @patch.object(Client, '_api_request')
    def test_create_omits_status(self, mock_req):
        mock_req.return_value = (mock_response(ACT_SCORE), mock_sis_log())

        self.mixin.create_student_aptitude_assessment(
            STUDENT_GUID, ACT_GUID, '2025-10-04', 27)

        self.assertNotIn('status', self._sent_payload(mock_req))

    @patch.object(Client, '_api_request')
    def test_create_accepts_a_date_object(self, mock_req):
        mock_req.return_value = (mock_response(ACT_SCORE), mock_sis_log())

        self.mixin.create_student_aptitude_assessment(
            STUDENT_GUID, ACT_GUID, datetime.date(2025, 10, 4), 27)

        self.assertEqual(self._sent_payload(mock_req)['assessedOn'], '2025-10-04')

    @patch.object(Client, '_api_request')
    def test_create_returns_the_created_record(self, mock_req):
        mock_req.return_value = (mock_response(ACT_SCORE), mock_sis_log())

        result = self.mixin.create_student_aptitude_assessment(
            STUDENT_GUID, ACT_GUID, '2025-10-04', 27)

        self.assertEqual(result['id'], ACT_SCORE['id'])

    @patch.object(Client, '_api_request')
    def test_create_returns_none_on_failure(self, mock_req):
        mock_req.return_value = (mock_response({}, status_code=400), mock_sis_log())

        result = self.mixin.create_student_aptitude_assessment(
            STUDENT_GUID, ACT_GUID, '2025-10-04', 27)

        self.assertIsNone(result)

    @patch.object(Client, '_api_request')
    def test_create_includes_optional_fields_when_given(self, mock_req):
        mock_req.return_value = (mock_response(ACT_SCORE), mock_sis_log())

        self.mixin.create_student_aptitude_assessment(
            STUDENT_GUID, ACT_GUID, '2025-10-04', 27,
            percentiles=[{'value': 88, 'type': {'id': PCT_TYPE_1}}],
            form={'number': '3', 'name': 'Form C'},
            special_circumstances=[PCT_TYPE_2],
            source_id=PCT_TYPE_1,
            reported='official',
            preference='primary',
            override_title='ACT Comp (2025)',
            comment='Sent by the testing service.',
        )

        payload = self._sent_payload(mock_req)
        self.assertEqual(payload['percentiles'][0]['value'], 88)
        self.assertEqual(payload['form']['name'], 'Form C')
        self.assertEqual(payload['specialCircumstances'], [{'id': PCT_TYPE_2}])
        self.assertEqual(payload['source'], {'id': PCT_TYPE_1})
        self.assertEqual(payload['reported'], 'official')
        self.assertEqual(payload['overrideTitle'], 'ACT Comp (2025)')
        self.assertEqual(payload['comment'], 'Sent by the testing service.')

    @patch.object(Client, '_api_request')
    def test_create_never_sends_the_unsupported_update_field(self, mock_req):
        mock_req.return_value = (mock_response(ACT_SCORE), mock_sis_log())

        self.mixin.create_student_aptitude_assessment(
            STUDENT_GUID, ACT_GUID, '2025-10-04', 27)

        self.assertNotIn('update', self._sent_payload(mock_req))

    # ── percentile validation (the API rejects these) ──

    @patch.object(Client, '_api_request')
    def test_duplicate_percentile_types_are_rejected_before_the_call(self, mock_req):
        dupes = [
            {'value': 88, 'type': {'id': PCT_TYPE_1}},
            {'value': 91, 'type': {'id': PCT_TYPE_1}},
        ]

        with self.assertRaises(ValueError):
            self.mixin.create_student_aptitude_assessment(
                STUDENT_GUID, ACT_GUID, '2025-10-04', 27, percentiles=dupes)

        mock_req.assert_not_called()

    @patch.object(Client, '_api_request')
    def test_percentile_over_100_is_rejected_before_the_call(self, mock_req):
        with self.assertRaises(ValueError):
            self.mixin.create_student_aptitude_assessment(
                STUDENT_GUID, ACT_GUID, '2025-10-04', 27,
                percentiles=[{'value': 101, 'type': {'id': PCT_TYPE_1}}])

        mock_req.assert_not_called()

    # ── update ──

    @patch.object(Client, '_api_request')
    def test_update_puts_to_the_record_url(self, mock_req):
        mock_req.return_value = (mock_response(ACT_SCORE), mock_sis_log())

        self.mixin.update_student_aptitude_assessment(
            ACT_SCORE['id'], dict(ACT_SCORE))

        self.assertEqual(mock_req.call_args[0][0], 'PUT')
        self.assertIn(f"/api/student-aptitude-assessments/{ACT_SCORE['id']}",
                      mock_req.call_args[0][1])

    @patch.object(Client, '_api_request')
    def test_update_forces_the_root_id_to_match_the_url(self, mock_req):
        mock_req.return_value = (mock_response(ACT_SCORE), mock_sis_log())

        payload = dict(ACT_SCORE, id='stale-guid')
        self.mixin.update_student_aptitude_assessment(ACT_SCORE['id'], payload)

        self.assertEqual(self._sent_payload(mock_req)['id'], ACT_SCORE['id'])

    @patch.object(Client, '_api_request')
    def test_update_validates_percentiles(self, mock_req):
        payload = dict(ACT_SCORE, percentiles=[
            {'value': 5, 'type': {'id': PCT_TYPE_1}},
            {'value': 6, 'type': {'id': PCT_TYPE_1}},
        ])

        with self.assertRaises(ValueError):
            self.mixin.update_student_aptitude_assessment(ACT_SCORE['id'], payload)

        mock_req.assert_not_called()

    # ── delete ──

    @patch.object(Client, '_api_request')
    def test_delete_returns_true_on_204(self, mock_req):
        mock_req.return_value = (mock_response('', status_code=204), mock_sis_log())

        result = self.mixin.delete_student_aptitude_assessment(ACT_SCORE['id'])

        self.assertTrue(result)
        self.assertEqual(mock_req.call_args[0][0], 'DELETE')

    @patch.object(Client, '_api_request')
    def test_delete_returns_false_on_failure(self, mock_req):
        mock_req.return_value = (mock_response({}, status_code=400), mock_sis_log())

        self.assertFalse(
            self.mixin.delete_student_aptitude_assessment(ACT_SCORE['id']))

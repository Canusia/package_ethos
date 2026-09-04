"""Tests for AptitudeAssessmentsMixin — the assessment (test) catalog."""

from unittest.mock import patch, MagicMock

from django.test import TestCase

try:
    from ethos.ethos.library.aptitude_assessments import AptitudeAssessmentsMixin
except ImportError:
    from ethos.library.aptitude_assessments import AptitudeAssessmentsMixin


ACT_COMPOSITE = {
    'id': '7843496a-5cf4-45b0-9ba1-0b0a94188ee2',
    'code': 'ACTC',
    'title': 'ACT Composite',
    'type': 'admissions',
}

SAT_MATH = {
    'id': 'b1f0e2d3-4c5b-6a79-8d0e-1f2a3b4c5d6e',
    'code': 'SATM',
    'title': 'SAT Mathematics',
    'type': 'admissions',
}

MATH_PLACEMENT = {
    'id': 'c2e1f3a4-5d6c-7b8a-9e0f-2a3b4c5d6e7f',
    'code': 'MPLC',
    'title': 'Math Placement',
    'type': 'placement',
}

ALL_ASSESSMENTS = [ACT_COMPOSITE, SAT_MATH, MATH_PLACEMENT]


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


class AptitudeAssessmentsTest(TestCase):

    def setUp(self):
        self.mixin = AptitudeAssessmentsMixin.__new__(AptitudeAssessmentsMixin)
        self.mixin.URL = 'https://integrate.elluciancloud.com'
        self.mixin._cached_token = 'fake-token'
        self.mixin._token_expires_at = 9999999999

    # ── get_aptitude_assessments ──

    @patch.object(AptitudeAssessmentsMixin, '_api_request')
    def test_returns_all_assessments(self, mock_req):
        mock_req.return_value = (mock_response(ALL_ASSESSMENTS), mock_sis_log())

        result = self.mixin.get_aptitude_assessments()

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['code'], 'ACTC')

    @patch.object(AptitudeAssessmentsMixin, '_api_request')
    def test_hits_the_aptitude_assessments_endpoint(self, mock_req):
        mock_req.return_value = (mock_response(ALL_ASSESSMENTS), mock_sis_log())

        self.mixin.get_aptitude_assessments()

        url = mock_req.call_args[0][1]
        self.assertIn('/api/aptitude-assessments', url)

    @patch.object(AptitudeAssessmentsMixin, '_api_request')
    def test_paginates_until_total_count_reached(self, mock_req):
        page1 = [dict(ACT_COMPOSITE) for _ in range(500)]
        page2 = [dict(SAT_MATH) for _ in range(200)]
        headers = {'x-total-count': '700', 'x-max-page-size': '500'}
        mock_req.side_effect = [
            (mock_response(page1, headers=headers), mock_sis_log()),
            (mock_response(page2, headers=headers), mock_sis_log()),
        ]

        result = self.mixin.get_aptitude_assessments()

        self.assertEqual(len(result), 700)
        self.assertEqual(mock_req.call_count, 2)
        self.assertIn('offset=500', mock_req.call_args_list[1][0][1])

    @patch.object(AptitudeAssessmentsMixin, '_api_request')
    def test_returns_empty_list_on_error(self, mock_req):
        mock_req.return_value = (mock_response({'error': 'nope'}, status_code=500), mock_sis_log())

        result = self.mixin.get_aptitude_assessments()

        self.assertEqual(result, [])

    # ── get_aptitude_assessment_by_id ──

    @patch.object(AptitudeAssessmentsMixin, '_api_request')
    def test_by_id_returns_record(self, mock_req):
        mock_req.return_value = (mock_response(ACT_COMPOSITE), mock_sis_log())

        result = self.mixin.get_aptitude_assessment_by_id(ACT_COMPOSITE['id'])

        self.assertEqual(result['title'], 'ACT Composite')
        self.assertIn(f"/api/aptitude-assessments/{ACT_COMPOSITE['id']}", mock_req.call_args[0][1])

    @patch.object(AptitudeAssessmentsMixin, '_api_request')
    def test_by_id_returns_none_when_not_found(self, mock_req):
        mock_req.return_value = (mock_response({}, status_code=404), mock_sis_log())

        result = self.mixin.get_aptitude_assessment_by_id('missing-guid')

        self.assertIsNone(result)

    # ── get_aptitude_assessment_map ──

    @patch.object(AptitudeAssessmentsMixin, '_api_request')
    def test_map_is_keyed_by_guid(self, mock_req):
        mock_req.return_value = (mock_response(ALL_ASSESSMENTS), mock_sis_log())

        result = self.mixin.get_aptitude_assessment_map()

        self.assertEqual(result[ACT_COMPOSITE['id']]['title'], 'ACT Composite')
        self.assertEqual(set(result), {a['id'] for a in ALL_ASSESSMENTS})

    @patch.object(AptitudeAssessmentsMixin, '_api_request')
    def test_map_is_cached_across_calls(self, mock_req):
        mock_req.return_value = (mock_response(ALL_ASSESSMENTS), mock_sis_log())

        self.mixin.get_aptitude_assessment_map()
        self.mixin.get_aptitude_assessment_map()

        self.assertEqual(mock_req.call_count, 1)

    @patch.object(AptitudeAssessmentsMixin, '_api_request')
    def test_map_refresh_bypasses_the_cache(self, mock_req):
        mock_req.return_value = (mock_response(ALL_ASSESSMENTS), mock_sis_log())

        self.mixin.get_aptitude_assessment_map()
        self.mixin.get_aptitude_assessment_map(refresh=True)

        self.assertEqual(mock_req.call_count, 2)

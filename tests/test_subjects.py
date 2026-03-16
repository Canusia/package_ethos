from unittest.mock import patch, MagicMock

from django.test import TestCase

from django.conf import settings

if getattr(settings, 'DEBUG', False):
    from ethos.ethos.library.subjects import SubjectsMixin
else:
    from ethos.library.subjects import SubjectsMixin


SUBJECT_HUMR = {
    'id': '4c84a4c6-9403-4579-8b1d-adfdb8286bb5',
    'abbreviation': 'HUMR',
    'title': 'Human Resource Management',
}

SUBJECT_MATH = {
    'id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'abbreviation': 'MATH',
    'title': 'Mathematics',
}

SUBJECT_ENGL = {
    'id': 'b2c3d4e5-f6a7-8901-bcde-f12345678901',
    'abbreviation': 'ENGL',
    'title': 'English',
}

ALL_SUBJECTS = [SUBJECT_HUMR, SUBJECT_MATH, SUBJECT_ENGL]


def mock_response(data, status_code=200, headers=None):
    """Build a mock response object."""
    resp = MagicMock()
    resp.ok = status_code == 200
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


class SubjectsTest(TestCase):
    """Tests for SubjectsMixin."""

    def setUp(self):
        self.mixin = SubjectsMixin.__new__(SubjectsMixin)
        self.mixin.URL = 'https://integrate.elluciancloud.com'
        self.mixin._cached_token = 'fake-token'
        self.mixin._token_expires_at = 9999999999

    # ── get_subjects ──

    @patch.object(SubjectsMixin, '_api_request')
    def test_get_subjects_no_filters(self, mock_req):
        mock_req.return_value = (mock_response(ALL_SUBJECTS), mock_sis_log())

        result = self.mixin.get_subjects()

        self.assertEqual(len(result), len(ALL_SUBJECTS))
        url = mock_req.call_args[0][1]
        self.assertNotIn('criteria', url)

    @patch.object(SubjectsMixin, '_api_request')
    def test_get_subjects_returns_all_records(self, mock_req):
        mock_req.return_value = (mock_response(ALL_SUBJECTS), mock_sis_log())

        result = self.mixin.get_subjects()

        self.assertEqual(result[0]['abbreviation'], 'HUMR')
        self.assertEqual(result[1]['abbreviation'], 'MATH')
        self.assertEqual(result[2]['abbreviation'], 'ENGL')

    @patch.object(SubjectsMixin, '_api_request')
    def test_get_subjects_by_abbreviation(self, mock_req):
        mock_req.return_value = (mock_response([SUBJECT_HUMR]), mock_sis_log())

        result = self.mixin.get_subjects(abbreviation='HUMR')

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], 'Human Resource Management')
        url = mock_req.call_args[0][1]
        self.assertIn('criteria', url)
        self.assertIn('abbreviation', url)
        self.assertIn('HUMR', url)

    @patch.object(SubjectsMixin, '_api_request')
    def test_get_subjects_pagination(self, mock_req):
        page1 = list(range(500))
        page2 = list(range(200))

        resp1 = mock_response(page1, headers={
            'x-total-count': '700',
            'x-max-page-size': '500',
        })
        resp2 = mock_response(page2, headers={
            'x-total-count': '700',
            'x-max-page-size': '500',
        })

        mock_req.side_effect = [
            (resp1, mock_sis_log()),
            (resp2, mock_sis_log()),
        ]

        result = self.mixin.get_subjects()

        self.assertEqual(len(result), 700)
        self.assertEqual(mock_req.call_count, 2)
        second_url = mock_req.call_args_list[1][0][1]
        self.assertIn('offset=500', second_url)

    @patch.object(SubjectsMixin, '_api_request')
    def test_get_subjects_pagination_with_filter(self, mock_req):
        page1 = list(range(500))
        page2 = list(range(100))

        resp1 = mock_response(page1, headers={
            'x-total-count': '600',
            'x-max-page-size': '500',
        })
        resp2 = mock_response(page2, headers={
            'x-total-count': '600',
            'x-max-page-size': '500',
        })

        mock_req.side_effect = [
            (resp1, mock_sis_log()),
            (resp2, mock_sis_log()),
        ]

        result = self.mixin.get_subjects(abbreviation='MATH')

        self.assertEqual(len(result), 600)
        # Both URLs should contain the criteria filter
        first_url = mock_req.call_args_list[0][0][1]
        second_url = mock_req.call_args_list[1][0][1]
        self.assertIn('criteria', first_url)
        self.assertIn('criteria', second_url)
        self.assertIn('offset=500', second_url)

    @patch.object(SubjectsMixin, '_api_request')
    def test_get_subjects_single_page(self, mock_req):
        mock_req.return_value = (mock_response([SUBJECT_HUMR, SUBJECT_MATH]), mock_sis_log())

        result = self.mixin.get_subjects()

        self.assertEqual(len(result), 2)
        self.assertEqual(mock_req.call_count, 1)

    @patch.object(SubjectsMixin, '_api_request')
    def test_get_subjects_api_error(self, mock_req):
        mock_req.return_value = (mock_response({'error': 'bad'}, status_code=400), mock_sis_log())

        result = self.mixin.get_subjects()

        self.assertEqual(result, [])

    @patch.object(SubjectsMixin, '_api_request')
    def test_get_subjects_empty_result(self, mock_req):
        mock_req.return_value = (mock_response([]), mock_sis_log())

        result = self.mixin.get_subjects()

        self.assertEqual(result, [])

    # ── get_subject_by_id ──

    @patch.object(SubjectsMixin, '_api_request')
    def test_get_subject_by_id_found(self, mock_req):
        mock_req.return_value = (mock_response(SUBJECT_HUMR), mock_sis_log())

        result = self.mixin.get_subject_by_id('4c84a4c6-9403-4579-8b1d-adfdb8286bb5')

        self.assertEqual(result['abbreviation'], 'HUMR')
        self.assertEqual(result['title'], 'Human Resource Management')
        url = mock_req.call_args[0][1]
        self.assertIn('/api/subjects/4c84a4c6', url)

    @patch.object(SubjectsMixin, '_api_request')
    def test_get_subject_by_id_not_found(self, mock_req):
        mock_req.return_value = (mock_response({'error': 'not found'}, status_code=404), mock_sis_log())

        result = self.mixin.get_subject_by_id('nonexistent-guid')

        self.assertIsNone(result)

    @patch.object(SubjectsMixin, '_api_request')
    def test_get_subject_by_id_url_format(self, mock_req):
        mock_req.return_value = (mock_response(SUBJECT_MATH), mock_sis_log())

        self.mixin.get_subject_by_id('a1b2c3d4-e5f6-7890-abcd-ef1234567890')

        url = mock_req.call_args[0][1]
        self.assertEqual(url, 'https://integrate.elluciancloud.com/api/subjects/a1b2c3d4-e5f6-7890-abcd-ef1234567890')

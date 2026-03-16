from unittest.mock import patch, MagicMock

from django.test import TestCase

try:
    from ethos.ethos.library.academic_periods import AcademicPeriodsMixin
except ImportError:
    from ethos.library.academic_periods import AcademicPeriodsMixin


YEAR_2020 = {
    'id': '0307e986-df02-4850-b5b8-b8519203f814',
    'code': '2020',
    'title': '2019-2020',
    'category': {'type': 'year'},
    'startOn': '2020-01-01T00:00:00+00:00',
    'endOn': '2020-12-31T00:00:00+00:00',
}

TERM_SPRING = {
    'id': '9dfd0b62-efbf-4597-afbc-91cc311915e5',
    'code': '202020',
    'title': 'Spring Quarter 2020',
    'category': {
        'type': 'term',
        'parent': {'id': '0307e986-df02-4850-b5b8-b8519203f814'},
    },
    'startOn': '2020-03-30T00:00:00+00:00',
    'endOn': '2020-06-12T00:00:00+00:00',
}

TERM_FALL = {
    'id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
    'code': '202030',
    'title': 'Fall Quarter 2020',
    'category': {
        'type': 'term',
        'parent': {'id': '0307e986-df02-4850-b5b8-b8519203f814'},
    },
    'startOn': '2020-09-01T00:00:00+00:00',
    'endOn': '2020-12-15T00:00:00+00:00',
}

TERM_OTHER_PARENT = {
    'id': 'ffffffff-1111-2222-3333-444444444444',
    'code': '202110',
    'title': 'Winter Quarter 2021',
    'category': {
        'type': 'term',
        'parent': {'id': 'dddddddd-0000-0000-0000-000000000000'},
    },
}

SUBTERM_A = {
    'id': '11111111-2222-3333-4444-555555555555',
    'code': '315',
    'title': 'Summer Special 1',
    'category': {
        'type': 'subterm',
        'parent': {'id': '9dfd0b62-efbf-4597-afbc-91cc311915e5'},
    },
}

SUBTERM_B = {
    'id': '66666666-7777-8888-9999-aaaaaaaaaaaa',
    'code': '316',
    'title': 'Summer Special 2',
    'category': {
        'type': 'subterm',
        'parent': {'id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'},
    },
}

SUBTERM_OTHER_PARENT = {
    'id': 'bbbbbbbb-cccc-dddd-eeee-ffffffffffff',
    'code': '999',
    'title': 'Other Subterm',
    'category': {
        'type': 'subterm',
        'parent': {'id': 'ffffffff-1111-2222-3333-444444444444'},
    },
}

ALL_TERMS = [TERM_SPRING, TERM_FALL, TERM_OTHER_PARENT]
ALL_SUBTERMS = [SUBTERM_A, SUBTERM_B, SUBTERM_OTHER_PARENT]
ALL_PERIODS = [YEAR_2020, *ALL_TERMS, *ALL_SUBTERMS]


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


class AcademicPeriodsTest(TestCase):
    """Tests for AcademicPeriodsMixin."""

    def setUp(self):
        self.mixin = AcademicPeriodsMixin.__new__(AcademicPeriodsMixin)
        self.mixin.URL = 'https://integrate.elluciancloud.com'
        self.mixin._cached_token = 'fake-token'
        self.mixin._token_expires_at = 9999999999

    # ── get_academic_periods ──

    @patch.object(AcademicPeriodsMixin, '_api_request')
    def test_get_academic_periods_no_filters(self, mock_req):
        mock_req.return_value = (mock_response(ALL_PERIODS), mock_sis_log())

        result = self.mixin.get_academic_periods()

        self.assertEqual(len(result), len(ALL_PERIODS))
        url = mock_req.call_args[0][1]
        self.assertNotIn('criteria', url)

    @patch.object(AcademicPeriodsMixin, '_api_request')
    def test_get_academic_periods_by_code(self, mock_req):
        mock_req.return_value = (mock_response([YEAR_2020]), mock_sis_log())

        result = self.mixin.get_academic_periods(code='2020')

        self.assertEqual(len(result), 1)
        url = mock_req.call_args[0][1]
        self.assertIn('criteria', url)
        self.assertIn('"code"', url)

    @patch.object(AcademicPeriodsMixin, '_api_request')
    def test_get_academic_periods_by_category(self, mock_req):
        mock_req.return_value = (mock_response(ALL_TERMS), mock_sis_log())

        result = self.mixin.get_academic_periods(category='term')

        self.assertEqual(len(result), len(ALL_TERMS))
        url = mock_req.call_args[0][1]
        self.assertIn('"type"', url)
        self.assertIn('"term"', url)

    @patch.object(AcademicPeriodsMixin, '_api_request')
    def test_get_academic_periods_code_and_category(self, mock_req):
        mock_req.return_value = (mock_response([YEAR_2020]), mock_sis_log())

        result = self.mixin.get_academic_periods(code='2020', category='year')

        url = mock_req.call_args[0][1]
        self.assertIn('"code"', url)
        self.assertIn('"year"', url)

    @patch.object(AcademicPeriodsMixin, '_api_request')
    def test_get_academic_periods_pagination(self, mock_req):
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

        result = self.mixin.get_academic_periods()

        self.assertEqual(len(result), 700)
        self.assertEqual(mock_req.call_count, 2)
        # Second call should have offset=500
        second_url = mock_req.call_args_list[1][0][1]
        self.assertIn('offset=500', second_url)

    @patch.object(AcademicPeriodsMixin, '_api_request')
    def test_get_academic_periods_api_error(self, mock_req):
        mock_req.return_value = (mock_response({'error': 'bad'}, status_code=400), mock_sis_log())

        result = self.mixin.get_academic_periods()

        self.assertEqual(result, [])

    # ── get_academic_period_id ──

    @patch.object(AcademicPeriodsMixin, 'get_academic_periods')
    def test_get_academic_period_id_found(self, mock_get):
        mock_get.return_value = [YEAR_2020]

        result = self.mixin.get_academic_period_id('2020')

        self.assertEqual(result, '0307e986-df02-4850-b5b8-b8519203f814')

    @patch.object(AcademicPeriodsMixin, 'get_academic_periods')
    def test_get_academic_period_id_not_found(self, mock_get):
        mock_get.return_value = []

        result = self.mixin.get_academic_period_id('9999')

        self.assertIsNone(result)

    # ── _is_guid ──

    def test_is_guid_valid(self):
        self.assertTrue(self.mixin._is_guid('0307e986-df02-4850-b5b8-b8519203f814'))

    def test_is_guid_invalid(self):
        self.assertFalse(self.mixin._is_guid('2020'))
        self.assertFalse(self.mixin._is_guid('23/SP'))
        self.assertFalse(self.mixin._is_guid('not-a-guid'))

    # ── _resolve_academic_period ──

    @patch.object(AcademicPeriodsMixin, '_api_request')
    def test_resolve_by_guid(self, mock_req):
        mock_req.return_value = (mock_response(YEAR_2020), mock_sis_log())

        result = self.mixin._resolve_academic_period('0307e986-df02-4850-b5b8-b8519203f814')

        self.assertEqual(result['code'], '2020')
        url = mock_req.call_args[0][1]
        self.assertIn('/api/academic-periods/0307e986', url)

    @patch.object(AcademicPeriodsMixin, 'get_academic_periods')
    def test_resolve_by_code(self, mock_get):
        mock_get.return_value = [YEAR_2020]

        result = self.mixin._resolve_academic_period('2020')

        self.assertEqual(result['id'], '0307e986-df02-4850-b5b8-b8519203f814')
        mock_get.assert_called_once_with(code='2020')

    @patch.object(AcademicPeriodsMixin, 'get_academic_periods')
    def test_resolve_not_found(self, mock_get):
        mock_get.return_value = []

        result = self.mixin._resolve_academic_period('9999')

        self.assertIsNone(result)

    # ── get_child_academic_periods ──

    @patch.object(AcademicPeriodsMixin, 'get_academic_periods')
    @patch.object(AcademicPeriodsMixin, '_resolve_academic_period')
    def test_children_from_year_depth_1(self, mock_resolve, mock_get):
        mock_resolve.return_value = YEAR_2020
        mock_get.return_value = ALL_TERMS

        result = self.mixin.get_child_academic_periods('2020', depth=1)

        # Should only return 2 terms parented to YEAR_2020, not TERM_OTHER_PARENT
        self.assertEqual(len(result), 2)
        ids = {r['id'] for r in result}
        self.assertIn(TERM_SPRING['id'], ids)
        self.assertIn(TERM_FALL['id'], ids)
        self.assertNotIn(TERM_OTHER_PARENT['id'], ids)

    @patch.object(AcademicPeriodsMixin, 'get_academic_periods')
    @patch.object(AcademicPeriodsMixin, '_resolve_academic_period')
    def test_children_from_year_depth_2(self, mock_resolve, mock_get):
        mock_resolve.return_value = YEAR_2020

        def side_effect(category=None, **kwargs):
            if category == 'term':
                return ALL_TERMS
            if category == 'subterm':
                return ALL_SUBTERMS
            return []

        mock_get.side_effect = side_effect

        result = self.mixin.get_child_academic_periods('2020', depth=2)

        # 2 terms + 2 subterms (excludes other-parent entries)
        self.assertEqual(len(result), 4)
        ids = {r['id'] for r in result}
        self.assertIn(TERM_SPRING['id'], ids)
        self.assertIn(TERM_FALL['id'], ids)
        self.assertIn(SUBTERM_A['id'], ids)
        self.assertIn(SUBTERM_B['id'], ids)
        self.assertNotIn(SUBTERM_OTHER_PARENT['id'], ids)

    @patch.object(AcademicPeriodsMixin, 'get_academic_periods')
    @patch.object(AcademicPeriodsMixin, '_resolve_academic_period')
    def test_children_by_code(self, mock_resolve, mock_get):
        mock_resolve.return_value = YEAR_2020
        mock_get.return_value = ALL_TERMS

        result = self.mixin.get_child_academic_periods('2020', depth=1)

        mock_resolve.assert_called_once_with('2020')
        self.assertEqual(len(result), 2)

    @patch.object(AcademicPeriodsMixin, '_resolve_academic_period')
    def test_children_unresolvable_parent(self, mock_resolve):
        mock_resolve.return_value = None

        result = self.mixin.get_child_academic_periods('9999')

        self.assertEqual(result, [])

    @patch.object(AcademicPeriodsMixin, '_resolve_academic_period')
    def test_children_unknown_category_type(self, mock_resolve):
        mock_resolve.return_value = {
            'id': 'some-id',
            'category': {'type': 'unknown'},
        }

        result = self.mixin.get_child_academic_periods('some-id')

        self.assertEqual(result, [])

    @patch.object(AcademicPeriodsMixin, 'get_academic_periods')
    @patch.object(AcademicPeriodsMixin, '_resolve_academic_period')
    def test_children_depth_capped_at_4(self, mock_resolve, mock_get):
        mock_resolve.return_value = YEAR_2020
        mock_get.return_value = []

        self.mixin.get_child_academic_periods('2020', depth=10)

        # hierarchy only has 2 levels below year (term, subterm)
        # so even with depth=10 it caps and only fetches what's available
        self.assertLessEqual(mock_get.call_count, 2)

    @patch.object(AcademicPeriodsMixin, 'get_academic_periods')
    @patch.object(AcademicPeriodsMixin, '_resolve_academic_period')
    def test_children_no_matches(self, mock_resolve, mock_get):
        mock_resolve.return_value = YEAR_2020
        # Return terms but none matching our parent
        mock_get.return_value = [TERM_OTHER_PARENT]

        result = self.mixin.get_child_academic_periods('2020', depth=2)

        self.assertEqual(result, [])

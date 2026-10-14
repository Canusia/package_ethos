"""Banner look-up behind the Banner Grade Push setting's Look up button."""
import json
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.test import TestCase
from django.urls import reverse

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

from .. import grade_push_lookup as lk
from ..views import grade_push as view_mod

REG = '02edce3a-eb91-455f-9afb-571e40feb169'
SECTION = '7ef5c6f6-4ac6-431b-91f7-c555812802d8'
SCHEME = '7994c96c-e328-48f1-90b6-51cc0cda99d0'
A = 'e405042c-5fbf-4a4f-acec-1b0a5e538d2c'
FINAL = 'f70332ec-52b3-461b-808f-903ad1aa1883'
PRIMARY = '15b603a4-8c11-48ca-8165-06f7f0955eca'
OTHER = '633e0304-ddf4-45ad-b0bb-03f755b01219'

OPTIONS = {'id': REG, 'section': {'id': SECTION},
           'studentGradeScheme': {'detail': {'id': SCHEME}, 'title': 'Standard UG Quarter'},
           'grades': [{'grade': {'id': A}, 'value': 'A'}]}
TYPES = [{'id': FINAL, 'code': 'FINAL', 'title': 'Final'}]
INSTRUCTORS = [{'instructor': {'id': PRIMARY}, 'instructorRole': 'primary'},
               {'instructor': {'id': OTHER}}]
PERSON = {'names': [{'fullName': 'Legal Name'},
                    {'fullName': 'Brock C Anderson', 'preference': 'preferred'}]}


def _resp(status, body):
    r = MagicMock(ok=200 <= status < 300, status_code=status)
    r.json.return_value = body
    return r


def _client(routes):
    """A fake Ethos client; `routes` maps a URL fragment to (status, body)."""
    client = MagicMock(URL='https://ethos')

    def api(method, url, message_type, **kwargs):
        for fragment, (status, body) in routes.items():
            if fragment in url:
                return _resp(status, body), MagicMock(pk=7)
        raise AssertionError(f'unexpected url {url}')
    client._api_request.side_effect = api
    return client


OK_ROUTES = {f'section-registrations/{REG}': (200, OPTIONS),
             'section-grade-types': (200, TYPES),
             'section-instructors': (200, INSTRUCTORS),
             f'persons/{PRIMARY}': (200, PERSON),
             f'persons/{OTHER}': (404, {})}


class LookupServiceTests(TestCase):
    def test_grade_options_shape_and_accept_header(self):
        client = _client(OK_ROUTES)
        got = lk.grade_options(client, REG)
        self.assertEqual(got, {'section': SECTION,
                               'scheme': {'id': SCHEME, 'title': 'Standard UG Quarter'},
                               'grades': [{'value': 'A', 'id': A}]})
        headers = client._api_request.call_args.kwargs['headers']
        self.assertEqual(headers['Accept'], lk.GRADE_OPTIONS_ACCEPT)

    def test_lookup_combines_everything(self):
        with patch.object(lk, '_grade_scale', return_value=['A', 'B']):
            got = lk.lookup(_client(OK_ROUTES), REG)
        self.assertEqual(got['registration'], REG)
        self.assertEqual(got['section'], SECTION)
        self.assertEqual(got['grade_options'], [{'value': 'A', 'id': A}])
        self.assertEqual(got['grade_types'], [{'id': FINAL, 'code': 'FINAL', 'title': 'Final'}])
        self.assertEqual(got['instructors'], [
            {'id': PRIMARY, 'name': 'Brock C Anderson', 'role': 'primary'},
            {'id': OTHER, 'name': OTHER, 'role': ''}])
        self.assertEqual(got['scale'], ['A', 'B'])
        self.assertEqual(set(got['current']), {'final_grade_type', 'grade_map', 'grade_submitted_by'})

    def test_banner_failure_raises_with_status(self):
        client = _client({f'section-registrations/{REG}': (404, {})})
        with self.assertRaises(lk.BannerLookupError) as ctx:
            lk.lookup(client, REG)
        self.assertEqual(ctx.exception.status, 404)

    def test_grade_types_failure_raises(self):
        routes = dict(OK_ROUTES, **{'section-grade-types': (500, {})})
        with self.assertRaises(lk.BannerLookupError):
            lk.lookup(_client(routes), REG)

    def test_timeout_raises_lookup_error_status_0(self):
        client = MagicMock(URL='https://ethos')
        client._api_request.side_effect = requests.Timeout('timed out')
        with self.assertRaises(lk.BannerLookupError) as ctx:
            lk.lookup(client, REG)
        self.assertEqual(ctx.exception.status, 0)
        self.assertIn('timed out', str(ctx.exception))
        self.assertNotIn('HTTP 0', str(ctx.exception))

    def test_non_json_200_raises_lookup_error(self):
        client = MagicMock(URL='https://ethos')
        resp = _resp(200, None)
        resp.json.side_effect = ValueError('no json')
        client._api_request.return_value = (resp, MagicMock(pk=7))
        with self.assertRaises(lk.BannerLookupError):
            lk.grade_options(client, REG)

    def test_wrong_shape_raises_lookup_error(self):
        with self.assertRaises(lk.BannerLookupError):
            lk.grade_options(_client({f'section-registrations/{REG}': (200, [])}), REG)
        routes = dict(OK_ROUTES, **{'section-instructors': (200, {})})
        with self.assertRaises(lk.BannerLookupError):
            lk.lookup(_client(routes), REG)


class LookupViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        Group.objects.get_or_create(name='ce')
        cls.ce = User.objects.create_user(username='gp_ce', email='gp_ce@example.com', password='x')
        cls.ce.groups.add(Group.objects.get(name='ce'))
        cls.other = User.objects.create_user(username='gp_x', email='gp_x@example.com', password='x')

    def setUp(self):
        if _login_history_post_login is not None:
            user_logged_in.disconnect(_login_history_post_login)
            self.addCleanup(user_logged_in.connect, _login_history_post_login)
        self.url = reverse('ethos:grade_push_lookup')

    def _get(self, user, registration=REG, client=None, error=None):
        self.client.force_login(user)
        with patch.object(view_mod, 'ethos_client_or_error',
                          return_value=(client, error)):
            return self.client.get(self.url, {'registration': registration})

    def test_refused_without_settings_access(self):
        self.assertEqual(self._get(self.other, client=_client(OK_ROUTES)).status_code, 403)

    def test_bad_guid_is_400_before_banner(self):
        client = _client(OK_ROUTES)
        resp = self._get(self.ce, registration='nope', client=client)
        self.assertEqual(resp.status_code, 400)
        client._api_request.assert_not_called()

    def test_success_returns_json(self):
        with patch.object(lk, '_grade_scale', return_value=['A']):
            resp = self._get(self.ce, client=_client(OK_ROUTES))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['section'], SECTION)

    def test_banner_failure_is_502_with_status_and_log(self):
        resp = self._get(self.ce, client=_client({f'section-registrations/{REG}': (404, {})}))
        self.assertEqual(resp.status_code, 502)
        body = resp.json()
        self.assertEqual(body['status'], 404)
        self.assertIn('/ce/ethos/logs/7/', body['log_url'])

    def test_missing_credentials_is_400(self):
        resp = self._get(self.ce, client=None, error='Ethos is not configured for this campus.')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('not configured', resp.json()['error'])

    def test_timeout_is_502(self):
        client = MagicMock(URL='https://ethos')
        client._api_request.side_effect = requests.Timeout('timed out')
        resp = self._get(self.ce, client=client)
        self.assertEqual(resp.status_code, 502)
        self.assertIn('timed out', resp.json()['error'])

    def test_unexpected_error_is_502(self):
        with patch.object(view_mod, 'lookup', side_effect=RuntimeError('boom')), \
                self.assertLogs(view_mod.logger, 'ERROR'):
            resp = self._get(self.ce, client=_client(OK_ROUTES))
        self.assertEqual(resp.status_code, 502)

    def test_missing_registration_param_is_400(self):
        self.client.force_login(self.ce)
        with patch.object(view_mod, 'ethos_client_or_error', return_value=(_client(OK_ROUTES), None)):
            self.assertEqual(self.client.get(self.url).status_code, 400)

"""package_ethos#3 (3): every Ethos HTTP call carries a timeout."""
import importlib.util
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from . import PKG

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
else:  # pragma: no cover - flat pip layout
    from ethos.library.ethos import Ethos

BASE_REQUESTS = f'{PKG}.library.base.requests'
REG_REQUESTS = f'{PKG}.library.registration.requests'


def _resp(ok=True, status=200, text='{}'):
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status
    resp.text = text
    resp.json.return_value = {}
    return resp


@override_settings(MULTI_CAMPUS=False)
@patch.object(Ethos, '_log', return_value=None)
@patch.object(Ethos, 'get_auth_token', return_value='t')
class ApiRequestTimeoutTests(SimpleTestCase):
    def test_default_timeout_on_every_method(self, _token, _log):
        with patch(BASE_REQUESTS) as req:
            for method in ('get', 'post', 'put', 'head', 'delete'):
                getattr(req, method).return_value = _resp()
            client = Ethos()
            for method in ('GET', 'POST', 'PUT', 'HEAD', 'DELETE'):
                client._api_request(method, 'https://x/api/y', 'm')
            for method in ('get', 'post', 'put', 'head', 'delete'):
                self.assertEqual(getattr(req, method).call_args.kwargs['timeout'], 30, method)

    @override_settings(ETHOS_REQUEST_TIMEOUT=7)
    def test_setting_overrides_default(self, _token, _log):
        with patch(BASE_REQUESTS) as req:
            req.get.return_value = _resp()
            Ethos()._api_request('GET', 'https://x/api/y', 'm')
            self.assertEqual(req.get.call_args.kwargs['timeout'], 7)

    def test_per_call_timeout_wins(self, _token, _log):
        with patch(BASE_REQUESTS) as req:
            req.get.return_value = _resp()
            Ethos()._api_request('GET', 'https://x/api/y', 'm', timeout=120)
            self.assertEqual(req.get.call_args.kwargs['timeout'], 120)

    def test_registration_direct_calls_have_timeout(self, _token, _log):
        with patch(REG_REQUESTS) as req, \
                patch.object(Ethos, '_load_sis_guids', return_value={}), \
                patch.object(Ethos, 'get_preferred_accept_header', return_value=None):
            req.post.return_value = _resp()
            Ethos().mirror_linked_registrations('B1', '202690', ['1'])
            self.assertEqual(req.post.call_args.kwargs['timeout'], 30)


@override_settings(MULTI_CAMPUS=False)
class AuthTimeoutTests(SimpleTestCase):
    def test_auth_has_timeout(self):
        with patch(BASE_REQUESTS) as req:
            req.post.return_value = _resp(ok=False, status=401)
            Ethos().get_auth_token()
            self.assertEqual(req.post.call_args.kwargs['timeout'], 30)

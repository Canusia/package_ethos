import importlib.util
import uuid
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings

from cis.campus_context import campus_context, NoCampusContext
from cis.models.course import Campus

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.credentials import credentials_for, EthosNotConfigured, DEFAULT_URL
    from ethos.ethos.library.ethos import Ethos
    BASE = 'ethos.ethos.library.base'
else:
    from ethos.credentials import credentials_for, EthosNotConfigured, DEFAULT_URL
    from ethos.library.ethos import Ethos
    BASE = 'ethos.library.base'


def _campus(code=None):
    code = code or f'{settings.CAMPUS_CODE_PREFIX}-{uuid.uuid4().hex[:6]}'
    return Campus.objects.create(name=f'C-{code}', code=code)


@override_settings(MULTI_CAMPUS=False, COLLEAGUE_AUTH_CODE='single-key', ETHOS_CREDENTIALS={})
class SingleCampusCredentialTests(TestCase):
    def test_uses_the_deployment_key(self):
        self.assertEqual(credentials_for(None), ('single-key', DEFAULT_URL))

    def test_client_without_campus_uses_the_deployment_key(self):
        client = Ethos()
        self.assertEqual((client.AUTH_CODE, client.URL), ('single-key', DEFAULT_URL))

    def test_explicit_campus_is_ignored(self):
        self.assertIsNone(Ethos(campus=_campus()).campus)

    def test_ambient_campus_is_ignored(self):
        with campus_context(_campus()):
            self.assertIsNone(Ethos().campus)

    def test_construction_runs_no_queries(self):
        with self.assertNumQueries(0):
            Ethos()


@override_settings(MULTI_CAMPUS=True)
class MultiCampusCredentialTests(TestCase):
    def setUp(self):
        self.a, self.b = _campus(), _campus()
        self.creds = {self.a.code: {'auth_code': 'key-a', 'url': 'https://a.example'},
                      self.b.code: {'auth_code': 'key-b'}}

    def test_each_campus_resolves_its_own_credentials(self):
        with override_settings(ETHOS_CREDENTIALS=self.creds):
            self.assertEqual(credentials_for(self.a), ('key-a', 'https://a.example'))
            self.assertEqual(credentials_for(self.b), ('key-b', DEFAULT_URL))

    def test_missing_or_empty_entry_is_not_configured(self):
        with override_settings(ETHOS_CREDENTIALS={self.a.code: {'auth_code': ''}}):
            with self.assertRaises(EthosNotConfigured):
                credentials_for(self.a)
            with self.assertRaises(EthosNotConfigured):
                credentials_for(self.b)

    def test_never_falls_back_to_the_deployment_key(self):
        with override_settings(ETHOS_CREDENTIALS={}, COLLEAGUE_AUTH_CODE='deployment-key'):
            with self.assertRaises(EthosNotConfigured):
                Ethos(campus=self.a)

    def test_no_campus_raises(self):
        with override_settings(ETHOS_CREDENTIALS=self.creds):
            with self.assertRaises(NoCampusContext):
                Ethos()

    def test_ambient_campus_is_used(self):
        with override_settings(ETHOS_CREDENTIALS=self.creds), campus_context(self.b):
            client = Ethos()
        self.assertEqual((client.campus, client.AUTH_CODE), (self.b, 'key-b'))

    def test_explicit_campus_beats_the_ambient_one(self):
        with override_settings(ETHOS_CREDENTIALS=self.creds), campus_context(self.b):
            self.assertEqual(Ethos(campus=self.a).AUTH_CODE, 'key-a')

    def test_two_campuses_never_share_a_key_or_token(self):
        def fake_post(url, headers=None, **kw):
            resp = mock.Mock(ok=True)
            resp.text = f"token-for-{headers['Authorization'].split()[-1]}"
            return resp
        with override_settings(ETHOS_CREDENTIALS=self.creds), \
                mock.patch(f'{BASE}.requests.post', side_effect=fake_post) as post, \
                mock.patch(f'{BASE}.jwt.decode', return_value={'exp': 9999999999}):
            ca, cb = Ethos(campus=self.a), Ethos(campus=self.b)
            self.assertEqual(ca.get_auth_token(), 'token-for-key-a')
            self.assertEqual(cb.get_auth_token(), 'token-for-key-b')
            self.assertEqual(ca.get_auth_token(), 'token-for-key-a')  # cached, per instance
        self.assertEqual([c.args[0] for c in post.call_args_list],
                         ['https://a.example/auth', f'{DEFAULT_URL}/auth'])

import importlib.util
import uuid
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings

from cis.models.course import Campus

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
    BASE = 'ethos.ethos.library.base'
    REGISTRATION = 'ethos.ethos.library.registration'
else:
    from ethos.library.ethos import Ethos
    BASE = 'ethos.library.base'
    REGISTRATION = 'ethos.library.registration'


def _campus():
    code = f'{settings.CAMPUS_CODE_PREFIX}-{uuid.uuid4().hex[:6]}'
    return Campus.objects.create(name=f'C-{code}', code=code)


@override_settings(MULTI_CAMPUS=True)
class CampusLogTests(TestCase):
    def setUp(self):
        self.a = _campus()
        self.creds = {self.a.code: {'auth_code': 'key-a'}}

    def test_api_request_log_carries_the_campus(self):
        with override_settings(ETHOS_CREDENTIALS=self.creds):
            client = Ethos(campus=self.a)
            with mock.patch(f'{BASE}.requests.get',
                            return_value=mock.Mock(status_code=200, text='[]')), \
                    mock.patch.object(Ethos, 'get_auth_token', return_value='t'):
                _resp, log = client._api_request('GET', 'https://x/api/y', 'test')
        self.assertEqual(log.campus, self.a)

    def test_registration_log_carries_the_campus(self):
        with override_settings(ETHOS_CREDENTIALS=self.creds):
            client = Ethos(campus=self.a)
            with mock.patch(f'{REGISTRATION}.requests.post',
                            return_value=mock.Mock(ok=False, status_code=500, text='x')), \
                    mock.patch.object(Ethos, 'get_auth_token', return_value='t'):
                ok, log = client.mirror_linked_registrations('B1', '202610', ['1'])
        self.assertFalse(ok)
        self.assertEqual(log.campus, self.a)

    @override_settings(MULTI_CAMPUS=False, COLLEAGUE_AUTH_CODE='k')
    def test_single_campus_log_has_no_campus(self):
        client = Ethos()
        with mock.patch(f'{BASE}.requests.get',
                        return_value=mock.Mock(status_code=200, text='[]')), \
                mock.patch.object(Ethos, 'get_auth_token', return_value='t'):
            _resp, log = client._api_request('GET', 'https://x/api/y', 'test')
        self.assertIsNone(log.campus)

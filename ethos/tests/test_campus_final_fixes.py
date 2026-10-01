"""ETHOS-01 final review fixes (package_ethos#4): C1 (client-campus settings),
I2 (record-campus CE views) and M1 (poll/process report errors as CommandError)."""
import importlib.util
import json
import uuid
from io import StringIO
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase, override_settings

from cis.campus_context import campus_context, current_campus_or_none
from cis.models.course import Campus, Cohort, Course
from cis.models.settings import Setting
from cis.models.term import AcademicYear

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
    from ethos.ethos.views.courses import update_from_ethos, lookup_by_title
    from ethos.ethos.views.academic_periods import lookup_guid
    P = 'ethos.ethos'
else:
    from ethos.library.ethos import Ethos
    from ethos.views.courses import update_from_ethos, lookup_by_title
    from ethos.views.academic_periods import lookup_guid
    P = 'ethos'

SIS_KEY = 'cis.settings.sis_settings'
MSG = 'Ethos is not configured for this campus'


def _campus():
    code = f'{settings.CAMPUS_CODE_PREFIX}-{uuid.uuid4().hex[:6]}'
    return Campus.objects.create(name=f'C-{code}', code=code)


def _guids(campus, value):
    Setting.objects.create(key=SIS_KEY, campus=campus,
                           value={'guids': json.dumps({'academic_level': value})})


@override_settings(MULTI_CAMPUS=True)
class ClientCampusSettingsTests(TestCase):
    """C1 part 1: a client's campus-scoped settings are its own campus's."""

    def setUp(self):
        self.a, self.b = _campus(), _campus()
        _guids(self.a, 'level-a')
        _guids(self.b, 'level-b')
        self.creds = {self.a.code: {'auth_code': 'ka'}, self.b.code: {'auth_code': 'kb'}}

    def test_campus_b_client_loads_b_guids_under_ambient_a(self):
        with override_settings(ETHOS_CREDENTIALS=self.creds), campus_context(self.a):
            client = Ethos(campus=self.b)
            guids = client._load_sis_guids()
            # The ambient campus is restored afterwards.
            self.assertEqual(current_campus_or_none(), self.a)
        self.assertEqual(guids, {'academic_level': 'level-b'})

    def test_ambient_client_loads_ambient_guids(self):
        with override_settings(ETHOS_CREDENTIALS=self.creds), campus_context(self.a):
            self.assertEqual(Ethos()._load_sis_guids(), {'academic_level': 'level-a'})


@override_settings(MULTI_CAMPUS=False, COLLEAGUE_AUTH_CODE='k', ETHOS_CREDENTIALS={})
class SingleCampusSettingsTests(TestCase):
    def test_campus_less_client_reads_the_global_row(self):
        Setting.objects.create(key=SIS_KEY, campus=None,
                               value={'guids': json.dumps({'academic_level': 'g'})})
        self.assertEqual(Ethos()._load_sis_guids(), {'academic_level': 'g'})


def _recording(seen):
    def factory(campus=None):
        campus = campus or current_campus_or_none()
        seen.append(campus)
        client = mock.MagicMock()
        client.campus = campus
        client.get_course_by_id.return_value = None
        client.get_courses.return_value = []
        client.get_academic_periods.return_value = [{'id': 'g-1', 'title': 'T'}]
        return client
    return factory


@override_settings(MULTI_CAMPUS=True)
class RecordCampusViewTests(TestCase):
    """I2: CE views acting on a record build the client for the record's campus."""

    def setUp(self):
        self.a, self.b = _campus(), _campus()
        self.user = get_user_model().objects.create_superuser(
            username=f'su{uuid.uuid4().hex[:6]}@t.edu',
            email=f'su{uuid.uuid4().hex[:6]}@t.edu', password='x')
        cohort = Cohort.objects.create(name='Math', designator='MTH')
        self.course_b = Course.objects.create(cohort=cohort, catalog_number='101',
                                              name='MTH 101', title='Algebra', campus=self.b)
        # Legacy row: multi-campus mode refuses to save one, so null it afterwards.
        self.course_none = Course.objects.create(cohort=cohort, catalog_number='102',
                                                 name='MTH 102', title='Geo', campus=self.b)
        Course.objects.filter(pk=self.course_none.pk).update(campus=None)
        self.year_b = AcademicYear.objects.create(name='AY-B', code='2026', campus=self.b)

    def _post(self, ids):
        request = RequestFactory().post('/x/', data={'ids[]': [str(i) for i in ids]})
        request.user = self.user
        return request

    def _run(self, view, request, seen):
        with mock.patch(f'{P}.library.ethos.Ethos', _recording(seen)), campus_context(self.a):
            return view(request)

    def test_update_from_ethos_uses_the_courses_campus(self):
        seen = []
        self._run(update_from_ethos, self._post([self.course_b.pk]), seen)
        self.assertEqual(seen, [self.b])

    def test_lookup_by_title_uses_the_courses_campus(self):
        seen = []
        self._run(lookup_by_title, self._post([self.course_b.pk]), seen)
        self.assertEqual(seen, [self.b])

    def test_campus_less_course_falls_back_to_ambient(self):
        seen = []
        self._run(update_from_ethos, self._post([self.course_none.pk]), seen)
        self.assertEqual(seen, [self.a])

    def test_lookup_guid_uses_the_years_campus(self):
        seen = []
        request = RequestFactory().get('/x/', data={'ids[]': [str(self.year_b.pk)]})
        request.user = self.user
        self._run(lookup_guid, request, seen)
        self.assertEqual(seen, [self.b])

    def test_not_configured_record_campus_is_reported(self):
        with override_settings(ETHOS_CREDENTIALS={self.a.code: {'auth_code': 'ka'}}), \
                campus_context(self.a):
            response = update_from_ethos(self._post([self.course_b.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn(MSG, json.loads(response.content)['message'])


@override_settings(MULTI_CAMPUS=True)
class ConsumeCommandErrorTests(TestCase):
    """M1: poll/process report missing cursor/credentials as CommandError."""

    def setUp(self):
        self.a = _campus()

    def test_poll_without_a_cursor_is_a_command_error(self):
        with override_settings(ETHOS_CREDENTIALS={self.a.code: {'auth_code': 'ka'}}):
            with self.assertRaises(CommandError) as ctx:
                call_command('poll_ethos_messages', '--campus', self.a.code, '--force',
                             stdout=StringIO())
        self.assertIn('no Ethos queue cursor', str(ctx.exception))

    def test_poll_not_configured_is_a_command_error(self):
        with override_settings(ETHOS_CREDENTIALS={}):
            with self.assertRaises(CommandError):
                call_command('poll_ethos_messages', '--campus', self.a.code, '--peek',
                             stdout=StringIO())

    def test_process_is_an_ethos_command(self):
        if importlib.util.find_spec('ethos.ethos'):
            from ethos.ethos.command_base import EthosCommand
            from ethos.ethos.management.commands import process_ethos_messages, poll_ethos_messages
        else:
            from ethos.command_base import EthosCommand
            from ethos.management.commands import process_ethos_messages, poll_ethos_messages
        self.assertTrue(issubclass(process_ethos_messages.Command, EthosCommand))
        self.assertTrue(issubclass(poll_ethos_messages.Command, EthosCommand))

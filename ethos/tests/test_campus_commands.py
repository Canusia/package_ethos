"""Ethos commands and the section task run per campus (package_ethos#4)."""
import importlib.util
import uuid
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from cis.campus_context import current_campus_or_none
from cis.models.course import Campus, Cohort, Course

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos import tasks
    P = 'ethos.ethos'
else:
    from ethos import tasks
    P = 'ethos'


def _campus():
    code = f'{settings.CAMPUS_CODE_PREFIX}-{uuid.uuid4().hex[:6]}'
    return Campus.objects.create(name=f'C-{code}', code=code)


def _recording_ethos(seen, **methods):
    def factory(campus=None):
        # Like the real client: explicit campus, else the ambient one.
        campus = campus or current_campus_or_none()
        seen.append(campus)
        client = MagicMock()
        client.campus = campus
        for name, value in methods.items():
            getattr(client, name).return_value = value
        return client
    return factory


@override_settings(MULTI_CAMPUS=True)
class CampusCommandTests(TestCase):
    def setUp(self):
        self.a = _campus()

    def test_sync_without_campus_is_a_command_error(self):
        with self.assertRaises(CommandError):
            call_command('sync_ethos_resources', stdout=StringIO())

    def test_every_ethos_command_takes_campus(self):
        for name, args in [('import_courses_from_ethos', []),
                           ('import_sections_from_ethos', ['202620']),
                           ('import_subjects_from_ethos', []),
                           ('import_terms_from_ethos', ['2025']),
                           ('sync_ethos_resources', [])]:
            with self.subTest(name), self.assertRaises(CommandError) as ctx:
                call_command(name, *args, stdout=StringIO())
            self.assertIn('--campus', str(ctx.exception))

    def test_sync_builds_the_client_for_the_campus(self):
        seen = []
        factory = _recording_ethos(seen, get_available_resources=[])
        with patch(f'{P}.management.commands.sync_ethos_resources.Ethos', factory):
            call_command('sync_ethos_resources', campus=self.a.code, stdout=StringIO())
        self.assertEqual(seen, [self.a])

    def test_unconfigured_campus_is_a_command_error_not_a_traceback(self):
        with override_settings(ETHOS_CREDENTIALS={}):
            with self.assertRaises(CommandError) as ctx:
                call_command('sync_ethos_resources', campus=self.a.code, stdout=StringIO())
        self.assertIn(self.a.code, str(ctx.exception))

    def test_courses_import_stamps_the_campus(self):
        cohort = Cohort.objects.create(name='Math', designator='MTH', external_sis_id='sub-1')
        seen = []
        course = {'id': 'c-1', 'number': '101', 'title': 'Algebra',
                  'subject': {'id': 'sub-1', 'abbreviation': 'MTH'},
                  'credits': [{'minimum': 3}]}
        factory = _recording_ethos(seen, get_courses=[course])
        with patch(f'{P}.management.commands.import_courses_from_ethos.Ethos', factory):
            call_command('import_courses_from_ethos', create=True,
                         campus=self.a.code, stdout=StringIO())
        made = Course.objects.get(cohort=cohort, catalog_number='101')
        self.assertEqual(made.campus, self.a)
        self.assertEqual(seen, [self.a])


@override_settings(MULTI_CAMPUS=True)
class SectionTaskTests(TestCase):
    def test_task_builds_ethos_for_the_terms_campus(self):
        campus = _campus()
        term = SimpleNamespace(pk=1, external_sis_id='p-1', code='X',
                               academic_year=SimpleNamespace(campus=campus))
        seen = []
        factory = _recording_ethos(seen, get_sections=[])
        importer = MagicMock()
        importer.return_value.import_sections.return_value = {}
        with patch('cis.models.term.Term.objects.get', return_value=term), \
             patch(f'{P}.library.ethos.Ethos', factory), \
             patch('cis.services.tenant_services.get_tenant_service',
                   return_value=SimpleNamespace(SISImporter=importer)):
            tasks.import_sections_for_term.func(1)
        self.assertTrue(seen)
        self.assertTrue(all(c == campus for c in seen))

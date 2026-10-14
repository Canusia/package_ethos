"""The Banner Grade Push setting (form over the SIS GUIDS grade-push keys)."""
import json
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

from cis.models.settings import Setting
from cis.settings.sis_settings import sis_settings

from .. import apps as ethos_apps
from ..grade_push_lookup import BannerLookupError
from ..settings import grade_push as gp

TYPE = 'f70332ec-52b3-461b-808f-903ad1aa1883'
A = 'e405042c-5fbf-4a4f-acec-1b0a5e538d2c'
B = 'a87d8dda-ac99-4cff-af6e-09ae3989fcb4'
PERSON = '15b603a4-8c11-48ca-8165-06f7f0955eca'
REG = '02edce3a-eb91-455f-9afb-571e40feb169'


def _store(blob):
    Setting.objects.update_or_create(
        key=sis_settings.key, defaults={'value': {'guids': json.dumps(blob)}})


def _form(data):
    request = RequestFactory().post('/x?report_id=1')
    return gp.grade_push(request, data)


def _data(**over):
    data = {'sample_registration': '', 'final_grade_type': TYPE,
            'grade_map': json.dumps({'A': A}), 'grade_submitted_by': PERSON}
    data.update(over)
    return data


class FormTests(TestCase):
    def setUp(self):
        _store({'academic_level': 'x'})

    def test_key_is_sis_guids(self):
        self.assertEqual(gp.grade_push.key, sis_settings.key)

    def test_from_db_flattens(self):
        _store({'final_grade_type': {'id': TYPE}, 'grade_map': {'A': A},
                'grade_submitted_by': {'id': PERSON}})
        values = gp.grade_push.from_db()
        self.assertEqual(values['final_grade_type'], TYPE)
        self.assertEqual(json.loads(values['grade_map']), {'A': A})
        self.assertEqual(values['grade_submitted_by'], PERSON)
        self.assertEqual(values['sample_registration'], '')

    def test_from_db_on_corrupt_blob_is_blank_not_error(self):
        Setting.objects.filter(key=sis_settings.key).update(value={'guids': '{bad'})
        self.assertEqual(gp.grade_push.from_db()['final_grade_type'], '')

    def test_valid_form_normalises(self):
        form = _form(_data(final_grade_type=TYPE.upper(),
                           grade_map=json.dumps({' A ': A.upper()})))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['final_grade_type'], TYPE)
        self.assertEqual(form.cleaned_data['grade_map'], {'A': A})

    def test_rejects_bad_guids_and_bad_json(self):
        self.assertIn('final_grade_type', _form(_data(final_grade_type='x')).errors)
        self.assertIn('grade_submitted_by', _form(_data(grade_submitted_by='')).errors)
        self.assertIn('grade_map', _form(_data(grade_map='[1]')).errors)
        self.assertIn('grade_map', _form(_data(grade_map='{}')).errors)
        self.assertIn('grade_map', _form(_data(grade_map=json.dumps({'A': 'nope'}))).errors)
        self.assertIn('sample_registration', _form(_data(sample_registration='nope')).errors)

    def test_run_record_replaces_map_and_keeps_other_keys(self):
        _store({'academic_level': 'x', 'grade_map': {'Z': B}})
        form = _form(_data())
        self.assertTrue(form.is_valid(), form.errors)
        resp = form.run_record()
        self.assertEqual(json.loads(resp.content)['status'], 'success')
        blob = json.loads(Setting.objects.get(key=sis_settings.key).value['guids'])
        self.assertEqual(blob['grade_map'], {'A': A})
        self.assertEqual(blob['final_grade_type'], {'id': TYPE})
        self.assertEqual(blob['grade_submitted_by'], {'id': PERSON})
        self.assertEqual(blob['academic_level'], 'x')

    def test_run_record_refuses_corrupt_blob(self):
        Setting.objects.filter(key=sis_settings.key).update(value={'guids': '{bad'})
        form = _form(_data())
        self.assertTrue(form.is_valid(), form.errors)
        resp = form.run_record()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Setting.objects.get(key=sis_settings.key).value['guids'], '{bad')

    def test_install_writes_nothing(self):
        Setting.objects.filter(key=sis_settings.key).delete()
        gp.grade_push(RequestFactory().get('/x?report_id=1')).install()
        self.assertFalse(Setting.objects.filter(key=sis_settings.key).exists())


class SampleRegistrationCheckTests(TestCase):
    def _clean_with(self, options=None, error=None, client=True):
        fake = MagicMock() if client else None
        with patch.object(gp, 'ethos_client_or_error',
                          return_value=(fake, None if client else 'Ethos is not configured.')), \
             patch.object(gp, 'grade_options',
                          side_effect=error, return_value=options):
            form = _form(_data(sample_registration=REG,
                               grade_map=json.dumps({'A': A, 'B': B})))
            form.is_valid()  # validate while the patches are active; errors are cached
            return form

    def test_map_guid_not_in_options_is_an_error(self):
        form = self._clean_with({'grades': [{'value': 'A', 'id': A}], 'section': '', 'scheme': {}})
        self.assertFalse(form.is_valid())
        self.assertIn('B', str(form.errors['grade_map']))

    def test_all_options_present_is_valid(self):
        form = self._clean_with({'grades': [{'value': 'A', 'id': A}, {'value': 'B', 'id': B}],
                                 'section': '', 'scheme': {}})
        self.assertTrue(form.is_valid(), form.errors)

    def test_banner_failure_is_a_form_error(self):
        form = self._clean_with(error=BannerLookupError(503))
        self.assertFalse(form.is_valid())
        self.assertIn('503', str(form.errors['sample_registration']))

    def test_missing_credentials_is_a_form_error(self):
        form = self._clean_with(client=False)
        self.assertFalse(form.is_valid())
        self.assertIn('not configured', str(form.errors['sample_registration']))


class OverviewRenderTests(TestCase):
    def test_renders_escaped_table_and_flags(self):
        values = {'final_grade_type': TYPE, 'grade_submitted_by': '',
                  'grade_map': json.dumps({'<b>A</b>': A}), 'sample_registration': ''}
        with patch.object(gp, 'unmapped_grades', return_value=['P']):
            out = gp.grade_push.overview_render(values)
        self.assertIn('&lt;b&gt;A&lt;/b&gt;', out['grade_map'])
        self.assertNotIn('<b>A</b>', out['grade_map'])
        self.assertIn('P', out['grade_map'])
        self.assertIn('Not set', out['grade_submitted_by'])

    def test_registered_in_both_configurators(self):
        for config in (ethos_apps.EthosConfig, ethos_apps.DevEthosConfig):
            names = [c['name'] for c in config.CONFIGURATORS]
            self.assertIn('grade_push', names)

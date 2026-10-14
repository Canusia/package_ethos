"""grade_push_config: the shared load/apply used by the command and the setting form."""
import json

from django.test import TestCase, override_settings

from cis.models.settings import Setting
from cis.settings.sis_settings import sis_settings

from .. import grade_push_config as cfg

TYPE = '11111111-1111-1111-1111-111111111111'
GRADE_A = '22222222-2222-2222-2222-222222222222'
GRADE_B = '33333333-3333-3333-3333-333333333333'
PERSON = '44444444-4444-4444-4444-444444444444'


def _store(raw_guids, **extra):
    Setting.objects.update_or_create(
        key=sis_settings.key, defaults={'value': {'guids': raw_guids, **extra}})


def _blob():
    return json.loads(Setting.objects.get(key=sis_settings.key).value['guids'])


class LoadTests(TestCase):
    def test_flattens_the_three_keys(self):
        _store(json.dumps({'final_grade_type': {'id': TYPE}, 'grade_map': {'A': GRADE_A},
                           'grade_submitted_by': {'id': PERSON}, 'academic_level': 'x'}))
        self.assertEqual(cfg.load(), {'final_grade_type': TYPE, 'grade_map': {'A': GRADE_A},
                                      'grade_submitted_by': PERSON,
                                      'submitted_by_primary_instructor': False})

    def test_primary_instructor_source(self):
        _store(json.dumps({'grade_submitted_by': {'source': 'primary_instructor'}}))
        got = cfg.load()
        self.assertEqual(got['grade_submitted_by'], '')
        self.assertTrue(got['submitted_by_primary_instructor'])

    def test_unset_and_missing_row_are_blank(self):
        self.assertEqual(cfg.load(), {'final_grade_type': '', 'grade_map': {},
                                      'grade_submitted_by': '',
                                      'submitted_by_primary_instructor': False})

    def test_non_dict_values_are_blank_not_an_error(self):
        _store(json.dumps({'final_grade_type': TYPE, 'grade_submitted_by': PERSON,
                           'grade_map': {'A': GRADE_A}}))
        self.assertEqual(cfg.load(), {'final_grade_type': '', 'grade_map': {'A': GRADE_A},
                                      'grade_submitted_by': '',
                                      'submitted_by_primary_instructor': False})

    def test_corrupt_blob_raises(self):
        _store('{not json')
        with self.assertRaises(cfg.GradePushConfigError):
            cfg.load()


class ApplyTests(TestCase):
    def setUp(self):
        _store(json.dumps({'academic_level': 'x', 'grade_map': {'A': GRADE_A}}), note='keep')

    def test_merges_and_keeps_other_keys_and_fields(self):
        before, after = cfg.apply(final_grade_type=TYPE, grade_map={'B': GRADE_B},
                                  submitted_by=PERSON)
        self.assertEqual(before['grade_map'], {'A': GRADE_A})
        blob = _blob()
        self.assertEqual(blob, after)
        self.assertEqual(blob['grade_map'], {'A': GRADE_A, 'B': GRADE_B})
        self.assertEqual(blob['final_grade_type'], {'id': TYPE})
        self.assertEqual(blob['grade_submitted_by'], {'id': PERSON})
        self.assertEqual(blob['academic_level'], 'x')
        self.assertEqual(Setting.objects.get(key=sis_settings.key).value['note'], 'keep')

    def test_replace_drops_old_letters(self):
        cfg.apply(grade_map={'B': GRADE_B}, replace_grade_map=True)
        self.assertEqual(_blob()['grade_map'], {'B': GRADE_B})

    def test_clear_submitted_by(self):
        cfg.apply(submitted_by=PERSON)
        cfg.apply(clear_submitted_by=True)
        self.assertNotIn('grade_submitted_by', _blob())

    def test_primary_instructor_replaces_a_fixed_person_and_back(self):
        cfg.apply(submitted_by=PERSON)
        cfg.apply(submitted_by_primary_instructor=True)
        self.assertEqual(_blob()['grade_submitted_by'], {'source': 'primary_instructor'})
        cfg.apply(submitted_by=PERSON)
        self.assertEqual(_blob()['grade_submitted_by'], {'id': PERSON})

    def test_dry_run_writes_nothing(self):
        _, after = cfg.apply(final_grade_type=TYPE, dry_run=True)
        self.assertEqual(after['final_grade_type'], {'id': TYPE})
        self.assertNotIn('final_grade_type', _blob())

    def test_corrupt_blob_refused_and_untouched(self):
        _store('[1, 2]')
        with self.assertRaises(cfg.GradePushConfigError):
            cfg.apply(final_grade_type=TYPE)
        self.assertEqual(Setting.objects.get(key=sis_settings.key).value['guids'], '[1, 2]')

    def test_creates_the_row_when_missing(self):
        Setting.objects.filter(key=sis_settings.key).delete()
        cfg.apply(final_grade_type=TYPE)
        self.assertEqual(_blob(), {'final_grade_type': {'id': TYPE}})

    def test_save_lands_in_history(self):
        setting = Setting.objects.get(key=sis_settings.key)
        before = setting.history.count()
        cfg.apply(final_grade_type=TYPE)
        self.assertEqual(setting.history.count(), before + 1)

    def test_normalise_guid(self):
        self.assertEqual(cfg.normalise_guid(' ' + TYPE.upper() + ' '), TYPE)
        with self.assertRaises(ValueError):
            cfg.normalise_guid('nope')


@override_settings(MULTI_CAMPUS=True)
class ApplyCampusCreateTests(TestCase):
    """Creating the SIS GUIDS row on a multi-campus deployment stamps the served campus."""

    def setUp(self):
        from django.conf import settings
        from cis.models.course import Campus

        prefix = settings.CAMPUS_CODE_PREFIX
        self.a = Campus.objects.create(name=f'{prefix} CA', code=f'{prefix}-gca')
        self.b = Campus.objects.create(name=f'{prefix} CB', code=f'{prefix}-gcb')

    def test_apply_creates_the_row_for_the_current_campus_only(self):
        from cis.campus_context import campus_context

        Setting.objects.create(key=sis_settings.key, campus=self.b,
                               value={'guids': json.dumps({'academic_level': 'b'})})

        with campus_context(self.a):
            cfg.apply(final_grade_type=TYPE)

        row_a = Setting.objects.get(key=sis_settings.key, campus=self.a)
        self.assertEqual(json.loads(row_a.value['guids']), {'final_grade_type': {'id': TYPE}})
        row_b = Setting.objects.get(key=sis_settings.key, campus=self.b)
        self.assertEqual(json.loads(row_b.value['guids']), {'academic_level': 'b'})

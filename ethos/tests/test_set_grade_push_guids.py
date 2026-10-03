"""set_grade_push_guids: writes the grade-push keys into the SIS GUIDS setting."""
import json
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from cis.models.settings import Setting
from cis.settings.sis_settings import sis_settings

TYPE = '11111111-1111-1111-1111-111111111111'
GRADE_A = '22222222-2222-2222-2222-222222222222'
GRADE_B = '33333333-3333-3333-3333-333333333333'
PERSON = '44444444-4444-4444-4444-444444444444'


def _store(guids, **extra):
    Setting.objects.update_or_create(
        key=sis_settings.key,
        defaults={'value': {'guids': json.dumps(guids), **extra}})


def _guids():
    return json.loads(Setting.objects.get(key=sis_settings.key).value['guids'])


def _run(*args):
    out = StringIO()
    call_command('set_grade_push_guids', *args, stdout=out)
    return out.getvalue()


class SetGradePushGuidsTests(TestCase):
    def setUp(self):
        _store({'academic_level': 'x', 'grade_map': {'A': GRADE_A}}, note='keep')

    def test_dry_run_reports_and_saves_nothing(self):
        out = _run('--final-grade-type', TYPE, '--grade', f'B={GRADE_B}', '--dry-run')

        self.assertIn('Dry run', out)
        self.assertIn(TYPE, out)
        self.assertEqual(_guids(), {'academic_level': 'x', 'grade_map': {'A': GRADE_A}})

    def test_applies_keys_and_keeps_everything_else(self):
        _run('--final-grade-type', TYPE, '--grade', f'B={GRADE_B}',
             '--submitted-by', PERSON)

        guids = _guids()
        self.assertEqual(guids['final_grade_type'], {'id': TYPE})
        self.assertEqual(guids['grade_map'], {'A': GRADE_A, 'B': GRADE_B})
        self.assertEqual(guids['grade_submitted_by'], {'id': PERSON})
        self.assertEqual(guids['academic_level'], 'x')
        self.assertEqual(
            Setting.objects.get(key=sis_settings.key).value['note'], 'keep')

    def test_grade_map_file_merges_and_replace_drops_old_entries(self):
        path = self._map_file({' B ': GRADE_B})

        _run('--grade-map-file', path)
        self.assertEqual(_guids()['grade_map'], {'A': GRADE_A, 'B': GRADE_B})

        _run('--grade-map-file', path, '--replace-grade-map')
        self.assertEqual(_guids()['grade_map'], {'B': GRADE_B})

    def test_clear_submitted_by_removes_the_key(self):
        _run('--submitted-by', PERSON)
        _run('--clear-submitted-by')

        self.assertNotIn('grade_submitted_by', _guids())

    def test_rejects_a_value_that_is_not_a_guid(self):
        with self.assertRaises(CommandError):
            _run('--final-grade-type', 'FINAL')
        with self.assertRaises(CommandError):
            _run('--grade', 'A=not-a-guid')
        self.assertNotIn('final_grade_type', _guids())

    def test_rejects_a_malformed_grade_argument(self):
        with self.assertRaises(CommandError):
            _run('--grade', 'A')

    def test_refuses_to_overwrite_a_blob_that_is_not_valid_json(self):
        Setting.objects.filter(key=sis_settings.key).update(value={'guids': '{oops'})

        with self.assertRaises(CommandError):
            _run('--final-grade-type', TYPE)
        self.assertEqual(
            Setting.objects.get(key=sis_settings.key).value['guids'], '{oops')

    def test_nothing_to_apply_is_an_error(self):
        with self.assertRaises(CommandError):
            _run('--dry-run')

    def test_reports_remaining_config_errors(self):
        out = _run('--submitted-by', PERSON)

        self.assertIn('final_grade_type', out)

    def test_creates_the_setting_when_missing(self):
        Setting.objects.filter(key=sis_settings.key).delete()

        _run('--final-grade-type', TYPE, '--grade', f'A={GRADE_A}')

        self.assertEqual(_guids(), {'final_grade_type': {'id': TYPE},
                                    'grade_map': {'A': GRADE_A}})

    def test_save_is_recorded_in_setting_history(self):
        setting = Setting.objects.get(key=sis_settings.key)
        before = setting.history.count()

        _run('--final-grade-type', TYPE)

        self.assertEqual(setting.history.count(), before + 1)

    def _map_file(self, data):
        import tempfile
        f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        json.dump(data, f)
        f.close()
        self.addCleanup(__import__('os').unlink, f.name)
        return f.name


@override_settings(MULTI_CAMPUS=True)
class SetGradePushGuidsCampusTests(TestCase):
    """SIS GUIDS is one row per campus on a multi-campus deployment, so the
    command runs for one campus (--campus), like the other Ethos commands."""

    def setUp(self):
        from django.conf import settings
        from cis.models.course import Campus

        prefix = settings.CAMPUS_CODE_PREFIX
        self.a = Campus.objects.create(name=f'{prefix} GA', code=f'{prefix}-sga')
        self.b = Campus.objects.create(name=f'{prefix} GB', code=f'{prefix}-sgb')

    def _row(self, campus):
        return Setting.objects.get(key=sis_settings.key, campus=campus)

    def test_requires_a_campus(self):
        with self.assertRaises(CommandError):
            _run('--final-grade-type', TYPE)

    def test_writes_only_the_named_campus_row(self):
        Setting.objects.create(key=sis_settings.key, campus=self.a,
                               value={'guids': json.dumps({'academic_level': 'a'})})

        _run('--campus', self.a.code, '--final-grade-type', TYPE)
        _run('--campus', self.b.code, '--grade', f'A={GRADE_A}')

        a = json.loads(self._row(self.a).value['guids'])
        b = json.loads(self._row(self.b).value['guids'])
        self.assertEqual(a, {'academic_level': 'a', 'final_grade_type': {'id': TYPE}})
        self.assertEqual(b, {'grade_map': {'A': GRADE_A}})

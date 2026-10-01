import importlib.util
import uuid
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from cis.models.course import Campus

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.models import EthosConsumeCursor, EthosApplication, EthosMessage, EthosLog
else:
    from ethos.models import EthosConsumeCursor, EthosApplication, EthosMessage, EthosLog


def _campus():
    code = f'{settings.CAMPUS_CODE_PREFIX}-{uuid.uuid4().hex[:6]}'
    return Campus.objects.create(name=f'C-{code}', code=code)


def _run(*args):
    out = StringIO()
    call_command('assign_ethos_campus', *args, stdout=out)
    return out.getvalue()


def _message(campus=None):
    return EthosMessage.objects.create(queue_id=1, campus=campus)


@override_settings(MULTI_CAMPUS=True)
class AssignEthosCampusTests(TestCase):
    def setUp(self):
        self.a, self.b = _campus(), _campus()

    def _seed(self):
        cur = EthosConsumeCursor.objects.create(campus=None, last_processed_id=42)
        EthosApplication.objects.create(ethos_id='g1', name='N', campus=None)
        _message(None)
        _message(None)
        EthosLog.objects.create(method='GET', url='u', message_type='t', campus=None)
        return cur

    def test_dry_run_writes_nothing_but_prints_counts(self):
        self._seed()
        out = _run('--campus', self.a.code, '--dry-run')
        self.assertIn('EthosMessage', out)
        self.assertIn('2', out)
        self.assertEqual(EthosMessage.objects.filter(campus__isnull=False).count(), 0)
        self.assertEqual(EthosConsumeCursor.objects.filter(campus__isnull=False).count(), 0)

    def test_real_run_fills_only_null_rows(self):
        cur = self._seed()
        keep = _message(self.b)
        _run('--campus', self.a.code)
        keep.refresh_from_db()
        self.assertEqual(keep.campus, self.b)
        self.assertEqual(EthosMessage.objects.filter(campus=self.a).count(), 2)
        self.assertEqual(EthosLog.objects.filter(campus=self.a).count(), 1)
        self.assertEqual(EthosApplication.objects.filter(campus=self.a).count(), 1)
        cur.refresh_from_db()
        self.assertEqual(cur.campus, self.a)
        self.assertEqual(cur.last_processed_id, 42)
        self.assertEqual(EthosConsumeCursor.load(self.a).pk, cur.pk)

    def test_small_batch_size_still_covers_every_row(self):
        for _ in range(5):
            _message(None)
        _run('--campus', self.a.code, '--batch-size', '2')
        self.assertEqual(EthosMessage.objects.filter(campus__isnull=True).count(), 0)

    def test_unknown_code_raises(self):
        with self.assertRaises(CommandError):
            _run('--campus', 'NOPE-NOPE')

    def test_refuses_ambiguous_cursor_merge(self):
        EthosConsumeCursor.objects.create(campus=None, last_processed_id=1)
        EthosConsumeCursor.objects.create(campus=self.a, last_processed_id=9)
        _message(None)
        with self.assertRaises(CommandError) as cm:
            _run('--campus', self.a.code)
        self.assertIn('cursor', str(cm.exception))
        self.assertEqual(EthosMessage.objects.filter(campus__isnull=True).count(), 1)

    def test_application_clash_is_skipped_and_reported(self):
        EthosApplication.objects.create(ethos_id='g1', name='mine', campus=self.a)
        EthosApplication.objects.create(ethos_id='g1', name='orphan', campus=None)
        EthosApplication.objects.create(ethos_id='g2', name='ok', campus=None)
        out = _run('--campus', self.a.code)
        self.assertIn('skipped', out)
        self.assertTrue(EthosApplication.objects.filter(name='orphan', campus__isnull=True).exists())
        self.assertTrue(EthosApplication.objects.filter(name='ok', campus=self.a).exists())

    def test_runs_in_single_campus_mode_too(self):
        _message(None)
        with override_settings(MULTI_CAMPUS=False):
            _run('--campus', self.a.code)
        self.assertEqual(EthosMessage.objects.filter(campus=self.a).count(), 1)

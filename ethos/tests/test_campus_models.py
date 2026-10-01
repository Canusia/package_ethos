import importlib.util
import uuid

from django.conf import settings
from django.test import TestCase, override_settings

from cis.campus_context import campus_context
from cis.models.course import Campus

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.models import EthosConsumeCursor, EthosApplication, EthosLog
    from ethos.ethos.campus import for_campus
else:
    from ethos.models import EthosConsumeCursor, EthosApplication, EthosLog
    from ethos.campus import for_campus


def _campus(code=None):
    code = code or f'{settings.CAMPUS_CODE_PREFIX}-{uuid.uuid4().hex[:6]}'
    return Campus.objects.create(name=f'C-{code}', code=code)


@override_settings(MULTI_CAMPUS=True)
class CampusModelTests(TestCase):
    def setUp(self):
        self.a, self.b = _campus(), _campus()

    def test_one_cursor_per_campus(self):
        ca, cb = EthosConsumeCursor.load(self.a), EthosConsumeCursor.load(self.b)
        self.assertNotEqual(ca.pk, cb.pk)
        self.assertEqual(EthosConsumeCursor.load(self.a).pk, ca.pk)

    def test_same_ethos_id_under_two_campuses(self):
        EthosApplication.objects.create(ethos_id='g1', name='A', campus=self.a)
        EthosApplication.objects.create(ethos_id='g1', name='B', campus=self.b)

    def test_for_campus_filters_to_the_current_campus(self):
        EthosLog.objects.create(method='GET', url='u', message_type='t', campus=self.a)
        EthosLog.objects.create(method='GET', url='u', message_type='t', campus=self.b)
        with campus_context(self.a):
            self.assertEqual(list(for_campus(EthosLog.objects.all()).values_list('campus', flat=True)),
                             [self.a.pk])


@override_settings(MULTI_CAMPUS=False)
class SingleCampusModelTests(TestCase):
    def test_for_campus_passes_through(self):
        EthosLog.objects.create(method='GET', url='u', message_type='t')
        self.assertEqual(for_campus(EthosLog.objects.all()).count(), 1)

    def test_load_without_campus_is_the_singleton(self):
        self.assertEqual(EthosConsumeCursor.load().pk, EthosConsumeCursor.load().pk)

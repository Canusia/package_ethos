import importlib.util
import uuid

from django.conf import settings
from django.test import TestCase, override_settings

from cis.models.course import Campus

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
    from ethos.ethos.models import EthosApplication, EthosRepresentation, EthosResource
    from ethos.ethos.views.resources import sync_resources
else:
    from ethos.library.ethos import Ethos
    from ethos.models import EthosApplication, EthosRepresentation, EthosResource
    from ethos.views.resources import sync_resources


def _campus():
    code = f'{settings.CAMPUS_CODE_PREFIX}-{uuid.uuid4().hex[:6]}'
    return Campus.objects.create(name=f'C-{code}', code=code)


APPS = [{'id': 'g1', 'name': 'App', 'resources': ['persons']}]


@override_settings(MULTI_CAMPUS=True)
class CatalogueMultiCampusTests(TestCase):
    def setUp(self):
        self.a, self.b = _campus(), _campus()

    def test_same_app_syncs_once_per_campus(self):
        sync_resources(APPS, campus=self.a)
        sync_resources(APPS, campus=self.b)
        self.assertEqual(EthosApplication.objects.filter(ethos_id='g1').count(), 2)

    def test_resync_leaves_other_campus_untouched(self):
        sync_resources(APPS, campus=self.a)
        sync_resources(APPS, campus=self.b)
        b_ids = set(EthosResource.objects.filter(application__campus=self.b).values_list('pk', flat=True))
        sync_resources(APPS, campus=self.a)
        self.assertEqual(EthosApplication.objects.filter(ethos_id='g1').count(), 2)
        self.assertEqual(
            set(EthosResource.objects.filter(application__campus=self.b).values_list('pk', flat=True)), b_ids)
        self.assertEqual(EthosResource.objects.filter(application__campus=self.a).count(), 1)

    def test_preferred_accept_header_is_per_campus(self):
        for campus, media in ((self.a, 'application/vnd.a+json'), (self.b, 'application/vnd.b+json')):
            sync_resources(APPS, campus=campus)
            res = EthosResource.objects.get(application__campus=campus, name='persons')
            rep = EthosRepresentation.objects.create(resource=res, x_media_type=media, methods=[])
            res.preferred_representation = rep
            res.save()
        creds = {c.code: {'auth_code': 'x'} for c in (self.a, self.b)}
        with override_settings(ETHOS_CREDENTIALS=creds):
            self.assertEqual(Ethos(campus=self.a).get_preferred_accept_header('persons'), 'application/vnd.a+json')
            self.assertEqual(Ethos(campus=self.b).get_preferred_accept_header('persons'), 'application/vnd.b+json')


@override_settings(MULTI_CAMPUS=False)
class CatalogueSingleCampusTests(TestCase):
    def test_upserts_by_ethos_id_among_campusless_rows(self):
        sync_resources(APPS)
        sync_resources([{'id': 'g1', 'name': 'Renamed', 'resources': ['persons', 'courses']}])
        self.assertEqual(EthosApplication.objects.count(), 1)
        app = EthosApplication.objects.get()
        self.assertIsNone(app.campus)
        self.assertEqual(app.name, 'Renamed')
        self.assertEqual(app.resources.count(), 2)

    def test_preferred_accept_header_unfiltered(self):
        sync_resources(APPS)
        res = EthosResource.objects.get(name='persons')
        rep = EthosRepresentation.objects.create(resource=res, x_media_type='application/vnd.x+json', methods=[])
        res.preferred_representation = rep
        res.save()
        self.assertEqual(Ethos().get_preferred_accept_header('persons'), 'application/vnd.x+json')

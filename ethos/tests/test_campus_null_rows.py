"""#14: superusers see Ethos rows with no campus; everyone else and every write stay per campus."""
import importlib.util
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from cis.campus_context import campus_context
from cis.models.course import Campus

from .test_campus_views import mock_ce_role

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.models import (
        EthosApplication, EthosLog, EthosMessage, EthosRepresentation, EthosResource,
    )
    from ethos.ethos.views.logs import EthosLogViewSet, log_detail
    from ethos.ethos.views.messages import EthosMessageViewSet, message_consume, message_detail
    from ethos.ethos.views.resources import (
        EthosResourceViewSet, resource_detail, resource_set_preferred,
    )
else:
    from ethos.models import (
        EthosApplication, EthosLog, EthosMessage, EthosRepresentation, EthosResource,
    )
    from ethos.views.logs import EthosLogViewSet, log_detail
    from ethos.views.messages import EthosMessageViewSet, message_consume, message_detail
    from ethos.views.resources import EthosResourceViewSet, resource_detail, resource_set_preferred

User = get_user_model()


def _campus():
    code = f'{settings.CAMPUS_CODE_PREFIX}-{uuid.uuid4().hex[:6]}'
    return Campus.objects.create(name=f'C-{code}', code=code)


def _user(superuser):
    name = f'u{uuid.uuid4().hex[:8]}@t.edu'
    if superuser:
        return User.objects.create_superuser(username=name, email=name, password='x')
    return User.objects.create_user(username=name, email=name, password='x', is_staff=True)


def _rows(response):
    data = response.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class NullCampusFixture(TestCase):

    def setUp(self):
        self.a, self.b = _campus(), _campus()
        self.su, self.staff = _user(True), _user(False)

        def message(queue_id, campus):
            return EthosMessage.objects.create(
                queue_id=queue_id, resource_name='r', resource_id=f'g{queue_id}',
                operation='replaced', payload={}, campus=campus)

        self.msg_a, self.msg_b, self.msg_none = message(1, self.a), message(2, self.b), message(3, None)
        self.log_a = EthosLog.objects.create(method='GET', url='https://x/a', message_type='t',
                                             campus=self.a)
        self.log_none = EthosLog.objects.create(method='GET', url='https://x/n', message_type='t',
                                                campus=None)
        app_a = EthosApplication.objects.create(ethos_id='ga', name='A', campus=self.a)
        app_none = EthosApplication.objects.create(ethos_id='gn', name='N', campus=None)
        self.res_a = EthosResource.objects.create(application=app_a, name='persons')
        self.res_none = EthosResource.objects.create(application=app_none, name='persons')

    def _api(self, viewset, user):
        request = APIRequestFactory().get('/x/')
        force_authenticate(request, user=user)
        with mock_ce_role(), campus_context(self.a):
            return _rows(viewset.as_view({'get': 'list'})(request))

    def _req(self, user, method='get', **kw):
        request = getattr(RequestFactory(), method)('/x/', **kw)
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def _view(self, view, user, pk, method='get', **kw):
        with campus_context(self.a):
            return view(self._req(user, method, **kw), pk=pk)


@override_settings(MULTI_CAMPUS=True, ETHOS_CREDENTIALS={})
class SuperuserSeesNullCampusTests(NullCampusFixture):

    def test_lists_add_null_campus_rows_with_a_marker(self):
        for viewset, own, none in (
            (EthosMessageViewSet, self.msg_a, self.msg_none),
            (EthosLogViewSet, self.log_a, self.log_none),
            (EthosResourceViewSet, self.res_a, self.res_none),
        ):
            with self.subTest(viewset=viewset.__name__):
                rows = {r['id']: r for r in self._api(viewset, self.su)}
                self.assertEqual(set(rows), {own.pk, none.pk})
                self.assertFalse(rows[own.pk]['no_campus'])
                self.assertTrue(rows[none.pk]['no_campus'])

    def test_other_campus_rows_stay_hidden(self):
        ids = {r['id'] for r in self._api(EthosMessageViewSet, self.su)}
        self.assertNotIn(self.msg_b.pk, ids)

    def test_detail_pages_open_with_the_marker(self):
        for view, obj in ((message_detail, self.msg_none), (log_detail, self.log_none),
                          (resource_detail, self.res_none)):
            with self.subTest(view=view.__name__):
                response = self._view(view, self.su, obj.pk)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'No campus', response.content)

    def test_null_campus_message_has_no_consume_button(self):
        content = self._view(message_detail, self.su, self.msg_none.pk).content
        self.assertNotIn(b'>Consume</button>', content)
        self.assertIn(b'assign_ethos_campus', content)
        own = self._view(message_detail, self.su, self.msg_a.pk).content
        self.assertIn(b'>Consume</button>', own)
        self.assertNotIn(b'No campus', own)

    def test_null_campus_resource_has_no_set_buttons(self):
        for res in (self.res_none, self.res_a):
            EthosRepresentation.objects.get_or_create(resource=res, x_media_type='application/json')
        content = self._view(resource_detail, self.su, self.res_none.pk).content
        self.assertNotIn(b'>Set</button>', content)
        own = self._view(resource_detail, self.su, self.res_a.pk).content
        self.assertIn(b'>Set</button>', own)

    def test_writes_stay_on_the_current_campus(self):
        with self.assertRaises(Http404):
            self._view(message_consume, self.su, self.msg_none.pk, method='post')
        with self.assertRaises(Http404):
            self._view(resource_set_preferred, self.su, self.res_none.pk, method='post',
                       data={'representation_id': ''})


@override_settings(MULTI_CAMPUS=True, ETHOS_CREDENTIALS={})
class NonSuperuserTests(NullCampusFixture):

    def test_lists_hide_null_campus_rows(self):
        for viewset, own in ((EthosMessageViewSet, self.msg_a), (EthosLogViewSet, self.log_a),
                             (EthosResourceViewSet, self.res_a)):
            with self.subTest(viewset=viewset.__name__):
                self.assertEqual({r['id'] for r in self._api(viewset, self.staff)}, {own.pk})

    def test_detail_of_null_campus_row_is_404(self):
        for view, obj in ((message_detail, self.msg_none), (log_detail, self.log_none),
                          (resource_detail, self.res_none)):
            with self.subTest(view=view.__name__), self.assertRaises(Http404):
                self._view(view, self.staff, obj.pk)


@override_settings(MULTI_CAMPUS=False)
class SingleCampusTests(NullCampusFixture):

    def test_everything_is_listed_and_nothing_is_marked(self):
        rows = self._api(EthosMessageViewSet, self.staff)
        self.assertEqual({r['id'] for r in rows}, {self.msg_a.pk, self.msg_b.pk, self.msg_none.pk})
        self.assertFalse(any(r['no_campus'] for r in rows))
        self.assertNotIn(b'No campus', self._view(message_detail, self.staff, self.msg_none.pk).content)

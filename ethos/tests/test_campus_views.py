"""CE views are per campus and never 500 when a campus has no Ethos credentials (#4)."""
import importlib.util
import json
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from cis.campus_context import campus_context
from cis.models.course import Campus

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.models import EthosLog, EthosMessage
    from ethos.ethos.views.messages import EthosMessageViewSet, message_detail
    from ethos.ethos.views.logs import EthosLogViewSet, log_detail
    from ethos.ethos.views.status import run_method
    from ethos.ethos.views.subjects import lookup_subjects
    from ethos.ethos.views.academic_periods import lookup_guid, lookup_academic_period
    from ethos.ethos.views.resources import resources_sync
else:
    from ethos.models import EthosLog, EthosMessage
    from ethos.views.messages import EthosMessageViewSet, message_detail
    from ethos.views.logs import EthosLogViewSet, log_detail
    from ethos.views.status import run_method
    from ethos.views.subjects import lookup_subjects
    from ethos.views.academic_periods import lookup_guid, lookup_academic_period
    from ethos.views.resources import resources_sync

User = get_user_model()
MSG = 'Ethos is not configured for this campus'


def _campus():
    code = f'{settings.CAMPUS_CODE_PREFIX}-{uuid.uuid4().hex[:6]}'
    return Campus.objects.create(name=f'C-{code}', code=code)


def _rows(response):
    data = response.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


@override_settings(MULTI_CAMPUS=True, ETHOS_CREDENTIALS={})
class CampusViewTests(TestCase):
    def setUp(self):
        self.a, self.b = _campus(), _campus()
        self.user = User.objects.create_superuser(
            username=f'su{uuid.uuid4().hex[:6]}@t.edu', email=f'su{uuid.uuid4().hex[:6]}@t.edu',
            password='x')
        self.msg_a = EthosMessage.objects.create(
            queue_id=1, resource_name='r', resource_id='g1', operation='replaced',
            payload={}, campus=self.a)
        self.msg_b = EthosMessage.objects.create(
            queue_id=2, resource_name='r', resource_id='g2', operation='replaced',
            payload={}, campus=self.b)
        self.log_a = EthosLog.objects.create(method='GET', url='https://x/a', message_type='t',
                                             campus=self.a)
        self.log_b = EthosLog.objects.create(method='GET', url='https://x/b', message_type='t',
                                             campus=self.b)

    def _api(self, viewset, campus):
        request = APIRequestFactory().get('/x/')
        force_authenticate(request, user=self.user)
        with campus_context(campus):
            return viewset.as_view({'get': 'list'})(request)

    def _req(self, method='get', path='/x/', **kw):
        request = getattr(RequestFactory(), method)(path, **kw)
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_messages_list_api_is_scoped_to_the_campus(self):
        with mock_ce_role():
            rows = _rows(self._api(EthosMessageViewSet, self.a))
        self.assertEqual([r['id'] for r in rows], [self.msg_a.pk])

    def test_logs_list_api_is_scoped_to_the_campus(self):
        rows = _rows(self._api(EthosLogViewSet, self.a))
        self.assertEqual([r['id'] for r in rows], [self.log_a.pk])

    def test_message_detail_of_another_campus_is_404(self):
        from django.http import Http404
        with campus_context(self.a):
            with self.assertRaises(Http404):
                message_detail(self._req(), self.msg_b.pk)
            self.assertEqual(message_detail(self._req(), self.msg_a.pk).status_code, 200)

    def test_log_detail_of_another_campus_is_404(self):
        from django.http import Http404
        with campus_context(self.a):
            with self.assertRaises(Http404):
                log_detail(self._req(), self.log_b.pk)

    def test_run_method_not_configured_is_a_json_error_not_a_500(self):
        request = self._req('post', '/x/', data=json.dumps(
            {'method_name': 'get_subjects', 'params': {}}), content_type='application/json')
        with campus_context(self.a):
            response = run_method(request)
        self.assertEqual(response.status_code, 409)
        self.assertIn(MSG, json.loads(response.content)['error'])

    def test_subject_lookup_not_configured_returns_display_message(self):
        with campus_context(self.a):
            response = lookup_subjects(self._req())
        self.assertEqual(response.status_code, 200)
        self.assertIn(MSG, json.loads(response.content)['message'])

    def test_academic_period_lookup_not_configured(self):
        with campus_context(self.a):
            response = lookup_academic_period(self._req(data={'code': '2026'}))
        self.assertEqual(response.status_code, 409)
        self.assertIn(MSG, json.loads(response.content)['message'])

    def test_resources_sync_not_configured_flashes_the_message(self):
        request = self._req('post')
        with campus_context(self.a):
            response = resources_sync(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(MSG + '.', [str(m) for m in request._messages])

    def test_course_actions_not_configured(self):
        if importlib.util.find_spec('ethos.ethos'):
            from ethos.ethos.views.courses import update_from_ethos
        else:
            from ethos.views.courses import update_from_ethos
        # The client is built per record now (its campus decides), so the course is real.
        from cis.models.course import Cohort, Course
        course = Course.objects.create(
            cohort=Cohort.objects.create(name='Math', designator='MTH'),
            catalog_number='101', name='MTH 101', title='Algebra', campus=self.a)
        request = self._req('post', data={'ids[]': [str(course.pk)]})
        with campus_context(self.a):
            response = update_from_ethos(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(MSG, json.loads(response.content)['message'])

    @override_settings(ETHOS_CREDENTIALS={})
    def test_configured_campus_gets_a_client(self):
        from unittest import mock
        creds = {self.a.code: {'auth_code': 'k'}}
        with override_settings(ETHOS_CREDENTIALS=creds), campus_context(self.a), \
                mock.patch('ethos.ethos.library.ethos.Ethos.get_subjects'
                           if importlib.util.find_spec('ethos.ethos')
                           else 'ethos.library.ethos.Ethos.get_subjects',
                           return_value=[{'id': '1'}]):
            response = lookup_subjects(self._req())
        self.assertEqual(json.loads(response.content)['status'], 'success')


@override_settings(MULTI_CAMPUS=False)
class SingleCampusViewTests(TestCase):
    def test_lists_are_not_filtered(self):
        user = User.objects.create_superuser(username='s@t.edu', email='s@t.edu', password='x')
        EthosLog.objects.create(method='GET', url='https://x/1', message_type='t')
        request = APIRequestFactory().get('/x/')
        force_authenticate(request, user=user)
        rows = _rows(EthosLogViewSet.as_view({'get': 'list'})(request))
        self.assertEqual(len(rows), 1)


def mock_ce_role():
    from unittest import mock
    pkg = 'ethos.ethos' if importlib.util.find_spec('ethos.ethos') else 'ethos'
    return mock.patch(f'{pkg}.views.messages.HasCERole.has_permission', return_value=True)

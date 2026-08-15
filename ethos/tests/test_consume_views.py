"""CE-gated browsing, dry-run, and consume actions."""
import importlib.util

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.test import TestCase, override_settings
from django.urls import reverse

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.models import EthosMessage
else:
    from ethos.models import EthosMessage

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

HANDLERS = {'section-registrations':
            'ethos.ethos.tests.test_consume_service.RecordingHandler'}

User = get_user_model()

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.consume.base import ConsumeHandler
else:
    from ethos.consume.base import ConsumeHandler


class PlanExplodingHandler(ConsumeHandler):
    """A handler whose plan() blows up — simulates a half-written handler
    being exercised via the dry-run panel."""
    resource_name = 'section-registrations'

    def plan(self, message):
        raise RuntimeError('boom from plan()')

    def apply(self, message, plan):
        raise AssertionError('apply() must never be reached in dry-run')


def _message(queue_id=1, **kwargs):
    defaults = dict(queue_id=queue_id, resource_name='section-registrations',
                    resource_id='guid-1', operation='replaced',
                    payload={'content': {'status': {
                        'sectionRegistrationStatusReason': 'dropped'}}})
    defaults.update(kwargs)
    return EthosMessage.objects.create(**defaults)


class MessageViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        # django_login_history's post_login signal handler blows up in tests
        # (force_login's fake request carries no usable IP). Disconnect for
        # the duration of the test case, mirroring
        # cis.tests.test_campus_viewset_permissions.
        if _login_history_post_login is not None:
            user_logged_in.disconnect(_login_history_post_login)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if _login_history_post_login is not None:
            user_logged_in.connect(_login_history_post_login)

    def setUp(self):
        self.message = _message()

    def _login_ce(self):
        """Create a CE user and log in.

        `_has_cis_role` checks `'ce' in user.get_roles()`, which is group-driven —
        mirror however ethos/tests or cis tests build a CE user. If no helper
        exists, add the user to the `ce` group.
        """
        from django.contrib.auth.models import Group
        user = User.objects.create_user(username='ce@test.edu', email='ce@test.edu',
                                        password='pw')
        group, _ = Group.objects.get_or_create(name='ce')
        user.groups.add(group)
        self.client.force_login(user)
        return user

    def test_list_requires_ce_role(self):
        resp = self.client.get(reverse('ethos:ethos_messages'))
        self.assertEqual(resp.status_code, 302)

    def test_list_renders_for_ce(self):
        self._login_ce()
        resp = self.client.get(reverse('ethos:ethos_messages'))
        self.assertEqual(resp.status_code, 200)

    def test_detail_renders_full_page(self):
        self._login_ce()
        resp = self.client.get(
            reverse('ethos:ethos_message_detail', args=[self.message.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'section-registrations')

    def test_detail_uses_partial_for_ajax(self):
        self._login_ce()
        resp = self.client.get(
            reverse('ethos:ethos_message_detail', args=[self.message.pk]),
            headers={'x-requested-with': 'XMLHttpRequest'})
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'ethos/messages/detail_partial.html')

    @override_settings(ETHOS_CONSUME_HANDLERS=HANDLERS)
    def test_dry_run_renders_plan_without_writing(self):
        self._login_ce()
        resp = self.client.post(
            reverse('ethos:ethos_message_dry_run', args=[self.message.pk]))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'registered')
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, EthosMessage.PENDING)

    @override_settings(ETHOS_CONSUME_HANDLERS=HANDLERS)
    def test_consume_applies_and_records(self):
        self._login_ce()
        resp = self.client.post(
            reverse('ethos:ethos_message_consume', args=[self.message.pk]))

        self.assertEqual(resp.status_code, 200)
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, EthosMessage.CONSUMED)

    def test_consume_rejects_get(self):
        self._login_ce()
        resp = self.client.get(
            reverse('ethos:ethos_message_consume', args=[self.message.pk]))
        self.assertEqual(resp.status_code, 405)

    def test_api_requires_authentication(self):
        # cis.middleware.LoginRequiredMiddleware wraps every non-whitelisted
        # view (including DRF viewsets) in `login_required`, so an
        # unauthenticated request never reaches the viewset's own permission
        # check — it is redirected (302) before DRF gets a chance to return
        # 401/403. The viewset still declares its own permission class as
        # defense in depth.
        resp = self.client.get('/ce/ethos/api/ethos-message/?format=json')
        self.assertEqual(resp.status_code, 302)

    def test_api_denies_authenticated_non_ce_user(self):
        # EthosMessage rows can carry a student's name in target_label (a
        # handler populates it), so a logged-in student/instructor must not
        # be able to list this API even though they pass authentication —
        # the pages themselves are gated to the 'ce' role and the API must
        # match.
        user = User.objects.create_user(username='student@test.edu',
                                        email='student@test.edu', password='pw')
        self.client.force_login(user)
        resp = self.client.get('/ce/ethos/api/ethos-message/?format=json')
        self.assertEqual(resp.status_code, 403)

    def test_api_allows_ce_user(self):
        self._login_ce()
        resp = self.client.get('/ce/ethos/api/ethos-message/?format=json')
        self.assertEqual(resp.status_code, 200)

    @override_settings(ETHOS_CONSUME_HANDLERS={
        'section-registrations': 'ethos.ethos.tests.test_consume_views.PlanExplodingHandler'})
    def test_dry_run_renders_plan_error_instead_of_500(self):
        # message_dry_run exists so an operator can safely inspect a
        # half-written handler. consume_message() deliberately re-raises
        # plan() failures in dry-run mode, so the view must catch that and
        # render it into the panel rather than surfacing a Django 500 page.
        self._login_ce()
        resp = self.client.post(
            reverse('ethos:ethos_message_dry_run', args=[self.message.pk]))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'plan() raised an error')
        self.assertContains(resp, 'boom from plan()')
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, EthosMessage.PENDING)

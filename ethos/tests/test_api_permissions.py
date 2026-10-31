"""Every ethos API viewset is CE-only, like the pages that display it (review I2).

Log URLs and descriptions carry student PII (persons?criteria=… with names and
credentials), so a logged-in student must not be able to list them directly."""
import importlib.util

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.test import TestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos import urls as ethos_urls
    from ethos.ethos.permissions import HasCERole
    from ethos.ethos.views import messages as messages_views
else:
    from ethos import urls as ethos_urls
    from ethos.permissions import HasCERole
    from ethos.views import messages as messages_views

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

User = get_user_model()

ENDPOINTS = ['/ce/ethos/api/ethos-log/?format=json',
             '/ce/ethos/api/ethos-resource/?format=json',
             '/ce/ethos/api/ethos-message/?format=json']


class ApiPermissionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        if _login_history_post_login is not None:
            user_logged_in.disconnect(_login_history_post_login)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if _login_history_post_login is not None:
            user_logged_in.connect(_login_history_post_login)

    def _login(self, *roles):
        user = User.objects.create_user(username='u@test.edu', email='u@test.edu', password='pw')
        for role in roles:
            user.groups.add(Group.objects.get_or_create(name=role)[0])
        self.client.force_login(user)

    def test_student_gets_403_on_every_api(self):
        self._login('student')
        for url in ENDPOINTS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_ce_user_can_read_every_api(self):
        self._login('ce')
        for url in ENDPOINTS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_every_registered_viewset_declares_has_ce_role(self):
        for prefix, viewset, _ in ethos_urls.router.registry:
            with self.subTest(viewset=viewset.__name__):
                self.assertIn(HasCERole, viewset.permission_classes)

    def test_old_import_path_still_works(self):
        self.assertIs(messages_views.HasCERole, HasCERole)

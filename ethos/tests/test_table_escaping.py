"""DataTables render functions escape every value they put into HTML (review I3).

Log paths are unquoted and can hold student-entered text (tvcc builds
persons?criteria= from a student's own first and last name), so a raw
``'<code>' + data + '</code>'`` runs a stored payload in the CE admin's session."""
import importlib.util
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.test import TestCase
from django.urls import reverse

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.models import EthosLog
else:
    from ethos.models import EthosLog

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

User = get_user_model()

PAGES = ['ethos:ethos_logs', 'ethos:ethos_resources', 'ethos:ethos_messages']
# A value concatenated into markup without going through esc(): `+ data +`, `+ row.x +`, `+ m.toUpperCase() +`.
RAW_CONCAT = re.compile(r"\+\s*(data|row\.\w+|m(\.\w+\(\))?)\s*(\+|;)")
HOSTILE = '<img src=x onerror=alert(1)>'


class TableEscapingTests(TestCase):
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

    def setUp(self):
        user = User.objects.create_user(username='ce@test.edu', email='ce@test.edu', password='pw')
        user.groups.add(Group.objects.get_or_create(name='ce')[0])
        self.client.force_login(user)

    def _script(self, name):
        resp = self.client.get(reverse(name))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        return html[html.index('.DataTable({'):]

    def test_no_render_function_concatenates_a_raw_value(self):
        for name in PAGES:
            with self.subTest(page=name):
                script = self._script(name)
                self.assertEqual(RAW_CONCAT.findall(script), [], name)
                self.assertIn('function esc(', self.client.get(reverse(name)).content.decode())

    def test_no_column_uses_the_default_html_render(self):
        # A `null` column spec makes DataTables insert the cell value as HTML.
        for name in PAGES:
            with self.subTest(page=name):
                columns = self._script(name).split('columns:', 1)[1]
                self.assertNotRegex(columns.split(']\n  });', 1)[0], r'^\s*null\s*,?\s*$|\n\s*null\s*,')

    def test_api_returns_a_hostile_path_as_data_for_the_escaped_render(self):
        EthosLog.objects.create(method='GET', url=f'https://x/api/persons?criteria={HOSTILE}',
                                message_type=HOSTILE, response_status=200)
        data = self.client.get('/ce/ethos/api/ethos-log/?format=json').json()
        row = data['results'][0] if isinstance(data, dict) else data[0]
        # The API hands the raw text over; only the escaped render keeps it inert.
        self.assertIn(HOSTILE, row['path'])
        self.assertEqual(row['message_type'], HOSTILE)

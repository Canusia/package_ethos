"""The CE menu injection for the Ethos Settings entry.

Exercises the migration's helper functions directly against a real Setting row
rather than replaying the migration, so the guards (missing row, missing SIS
group, already-present item) are all reachable.
"""
import importlib
import importlib.util
import json

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

# The module name starts with a digit, so it cannot be reached with `import`
# syntax — it has to be loaded by name.
_pkg = ('ethos.ethos' if importlib.util.find_spec('ethos.ethos') else 'ethos')
_migration = importlib.import_module(f'{_pkg}.migrations.0008_menu_ethos_settings')
add_settings_item = _migration.add_settings_item
remove_settings_item = _migration.remove_settings_item

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

from cis.models.settings import Setting  # noqa: E402

MENU_SETTING_KEY = 'cis.settings.menu'

SIS_GROUP = {
    'type': 'nav-item',
    'icon': 'fas fa-fw fa-user',
    'label': 'SIS',
    'name': 'ethos',
    'sub_menu': [
        {'label': 'All Resources', 'name': 'ethos_resources',
         'url': 'ethos:ethos_resources'},
        {'label': 'All Logs', 'name': 'ethos_logs',
         'url': 'ethos:ethos_logs'},
        {'label': 'Messages', 'name': 'ethos_messages',
         'url': 'ethos:ethos_messages'},
        {'label': 'Status', 'name': 'ethos_status',
         'url': 'ethos:ethos_status'},
    ],
}


def _ce_menu(items):
    return {'ce_menu': json.dumps(items)}


def _sub_names(setting):
    setting.refresh_from_db()
    items = json.loads(setting.value['ce_menu'])
    group = next(i for i in items if i.get('name') == 'ethos')
    return [s['name'] for s in group['sub_menu']]


class MenuMigrationTests(TestCase):
    def setUp(self):
        Setting.objects.filter(key=MENU_SETTING_KEY).delete()

    def _seed(self, items):
        return Setting.objects.create(key=MENU_SETTING_KEY, value=_ce_menu(items))

    def test_appends_settings_at_the_end_of_the_group(self):
        setting = self._seed([dict(SIS_GROUP)])

        add_settings_item(django_apps, None)

        self.assertEqual(
            _sub_names(setting),
            ['ethos_resources', 'ethos_logs', 'ethos_messages', 'ethos_status',
             'ethos_settings'],
        )

    def test_inserted_item_carries_the_right_url(self):
        setting = self._seed([dict(SIS_GROUP)])

        add_settings_item(django_apps, None)

        setting.refresh_from_db()
        group = next(i for i in json.loads(setting.value['ce_menu'])
                     if i.get('name') == 'ethos')
        item = next(s for s in group['sub_menu'] if s['name'] == 'ethos_settings')
        self.assertEqual(item['url'], 'ethos:ethos_settings')
        self.assertEqual(item['label'], 'Settings')

    def test_is_idempotent(self):
        setting = self._seed([dict(SIS_GROUP)])

        add_settings_item(django_apps, None)
        add_settings_item(django_apps, None)
        add_settings_item(django_apps, None)

        names = _sub_names(setting)
        self.assertEqual(names.count('ethos_settings'), 1)

    def test_reverse_removes_the_item(self):
        setting = self._seed([dict(SIS_GROUP)])
        add_settings_item(django_apps, None)

        remove_settings_item(django_apps, None)

        self.assertEqual(
            _sub_names(setting),
            ['ethos_resources', 'ethos_logs', 'ethos_messages', 'ethos_status'],
        )

    def test_reverse_is_idempotent(self):
        setting = self._seed([dict(SIS_GROUP)])
        add_settings_item(django_apps, None)

        remove_settings_item(django_apps, None)
        remove_settings_item(django_apps, None)

        self.assertEqual(
            _sub_names(setting),
            ['ethos_resources', 'ethos_logs', 'ethos_messages', 'ethos_status'],
        )

    def test_noop_when_sis_group_absent(self):
        """A tenant without the SIS nav group must not get an orphan group."""
        other = {'type': 'nav-item', 'name': 'users', 'label': 'Users'}
        setting = self._seed([other])

        add_settings_item(django_apps, None)

        setting.refresh_from_db()
        items = json.loads(setting.value['ce_menu'])
        self.assertEqual(items, [other])

    def test_noop_when_setting_row_missing(self):
        add_settings_item(django_apps, None)

        self.assertFalse(Setting.objects.filter(key=MENU_SETTING_KEY).exists())

    def test_noop_when_ce_menu_unparseable(self):
        setting = Setting.objects.create(
            key=MENU_SETTING_KEY, value={'ce_menu': 'not json{'})

        add_settings_item(django_apps, None)

        setting.refresh_from_db()
        self.assertEqual(setting.value['ce_menu'], 'not json{')

    def test_other_role_menus_are_untouched(self):
        setting = Setting.objects.create(key=MENU_SETTING_KEY, value={
            'ce_menu': json.dumps([dict(SIS_GROUP)]),
            'student_menu': json.dumps([{'name': 'home', 'label': 'Home'}]),
        })

        add_settings_item(django_apps, None)

        setting.refresh_from_db()
        self.assertEqual(
            json.loads(setting.value['student_menu']),
            [{'name': 'home', 'label': 'Home'}],
        )


class SettingsRedirectTests(TestCase):
    def setUp(self):
        if _login_history_post_login is not None:
            user_logged_in.disconnect(_login_history_post_login)
            self.addCleanup(user_logged_in.connect, _login_history_post_login)

    def test_redirects_ce_to_the_overview(self):
        Group.objects.get_or_create(name='ce')
        user = get_user_model().objects.create_user(
            username='es_ce', email='es_ce@example.com', password='x')
        user.groups.add(Group.objects.get(name='ce'))
        self.client.force_login(user)
        resp = self.client.get(reverse('ethos:ethos_settings'))
        self.assertRedirects(resp, reverse('cis:settings_overview', args=['ethos']),
                             fetch_redirect_response=False)

    def _ce_login(self):
        Group.objects.get_or_create(name='ce')
        user = get_user_model().objects.create_user(
            username='es_ce2', email='es_ce2@example.com', password='x')
        user.groups.add(Group.objects.get(name='ce'))
        self.client.force_login(user)

    def test_profile_present_redirects_to_the_overview(self):
        from ..views import settings_page
        self._ce_login()
        with patch.object(settings_page, 'profile_exists', return_value=True):
            resp = self.client.get(reverse('ethos:ethos_settings'))
        self.assertRedirects(resp, reverse('cis:settings_overview', args=['ethos']),
                             fetch_redirect_response=False)

    def test_profile_absent_redirects_to_the_status_page(self):
        from ..views import settings_page
        self._ce_login()
        with patch.object(settings_page, 'profile_exists', return_value=False):
            resp = self.client.get(reverse('ethos:ethos_settings'))
        self.assertRedirects(resp, reverse('ethos:ethos_status'),
                             fetch_redirect_response=False)

    def test_non_ce_user_is_turned_away(self):
        user = get_user_model().objects.create_user(
            username='es_x', email='es_x@example.com', password='x')
        self.client.force_login(user)
        resp = self.client.get(reverse('ethos:ethos_settings'))
        self.assertRedirects(resp, '/?next=/ce/ethos/settings/',
                             fetch_redirect_response=False)

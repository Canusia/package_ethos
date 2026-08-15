"""The CE menu injection for the ethos Messages page.

Exercises the migration's helper functions directly against a real Setting row
rather than replaying the migration, so the guards (missing row, missing SIS
group, already-present item) are all reachable.
"""
import importlib
import importlib.util
import json

from django.apps import apps as django_apps
from django.test import TestCase

# The module name starts with a digit, so it cannot be reached with `import`
# syntax — it has to be loaded by name.
_pkg = ('ethos.ethos' if importlib.util.find_spec('ethos.ethos') else 'ethos')
_migration = importlib.import_module(f'{_pkg}.migrations.0005_menu_ethos_messages')
add_messages_item = _migration.add_messages_item
remove_messages_item = _migration.remove_messages_item

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

    def test_inserts_messages_after_all_logs(self):
        setting = self._seed([dict(SIS_GROUP)])

        add_messages_item(django_apps, None)

        self.assertEqual(
            _sub_names(setting),
            ['ethos_resources', 'ethos_logs', 'ethos_messages', 'ethos_status'],
        )

    def test_inserted_item_carries_the_right_url(self):
        setting = self._seed([dict(SIS_GROUP)])

        add_messages_item(django_apps, None)

        setting.refresh_from_db()
        group = next(i for i in json.loads(setting.value['ce_menu'])
                     if i.get('name') == 'ethos')
        item = next(s for s in group['sub_menu'] if s['name'] == 'ethos_messages')
        self.assertEqual(item['url'], 'ethos:ethos_messages')
        self.assertEqual(item['label'], 'Messages')

    def test_is_idempotent(self):
        setting = self._seed([dict(SIS_GROUP)])

        add_messages_item(django_apps, None)
        add_messages_item(django_apps, None)
        add_messages_item(django_apps, None)

        names = _sub_names(setting)
        self.assertEqual(names.count('ethos_messages'), 1)

    def test_reverse_removes_the_item(self):
        setting = self._seed([dict(SIS_GROUP)])
        add_messages_item(django_apps, None)

        remove_messages_item(django_apps, None)

        self.assertEqual(
            _sub_names(setting),
            ['ethos_resources', 'ethos_logs', 'ethos_status'],
        )

    def test_reverse_is_idempotent(self):
        setting = self._seed([dict(SIS_GROUP)])
        add_messages_item(django_apps, None)

        remove_messages_item(django_apps, None)
        remove_messages_item(django_apps, None)

        self.assertEqual(
            _sub_names(setting),
            ['ethos_resources', 'ethos_logs', 'ethos_status'],
        )

    def test_noop_when_sis_group_absent(self):
        """A tenant without the SIS nav group must not get an orphan group."""
        other = {'type': 'nav-item', 'name': 'users', 'label': 'Users'}
        setting = self._seed([other])

        add_messages_item(django_apps, None)

        setting.refresh_from_db()
        items = json.loads(setting.value['ce_menu'])
        self.assertEqual(items, [other])

    def test_noop_when_setting_row_missing(self):
        add_messages_item(django_apps, None)

        self.assertFalse(Setting.objects.filter(key=MENU_SETTING_KEY).exists())

    def test_noop_when_ce_menu_unparseable(self):
        setting = Setting.objects.create(
            key=MENU_SETTING_KEY, value={'ce_menu': 'not json{'})

        add_messages_item(django_apps, None)

        setting.refresh_from_db()
        self.assertEqual(setting.value['ce_menu'], 'not json{')

    def test_appends_when_all_logs_item_is_absent(self):
        group = dict(SIS_GROUP)
        group['sub_menu'] = [
            {'label': 'Status', 'name': 'ethos_status',
             'url': 'ethos:ethos_status'},
        ]
        setting = self._seed([group])

        add_messages_item(django_apps, None)

        self.assertEqual(_sub_names(setting), ['ethos_status', 'ethos_messages'])

    def test_other_role_menus_are_untouched(self):
        setting = Setting.objects.create(key=MENU_SETTING_KEY, value={
            'ce_menu': json.dumps([dict(SIS_GROUP)]),
            'student_menu': json.dumps([{'name': 'home', 'label': 'Home'}]),
        })

        add_messages_item(django_apps, None)

        setting.refresh_from_db()
        self.assertEqual(
            json.loads(setting.value['student_menu']),
            [{'name': 'home', 'label': 'Home'}],
        )

"""Add the "Settings" sub-item to the CE sidebar's SIS nav group.

The portal menus are pulled (by ``cis.menu.draw_menu``) from the DB-backed
``cis.settings.menu`` Setting, keyed ``<role>_menu`` - each one a JSON *string*.
Editing the hardcoded lists in ``cis/menu.py`` does nothing; the DB row is the
source of truth. This data migration makes ``/ce/ethos/settings/`` (which
redirects to the Ethos Settings overview) reachable without hand-editing JSON
in the settings UI.

Only ``ce_menu`` is touched: the route is CE-role gated
(``ethos/urls.py`` wraps it in ``user_passes_test(_has_cis_role)``), so no
other role's menu should advertise it.

If the SIS group (``name == 'ethos'``) is absent, this no-ops rather than
creating it, as 0005 does: an orphan group holding only "Settings" would be
worse than none. README section 6 remains the path for that initial setup.

The item is appended at the end of the group, after Status.

Idempotent: re-running makes no further changes. No-ops if the menu Setting row
doesn't exist yet (e.g. before ``register_settings`` has run on a fresh
install). Depends on cis ``__first__`` so the ``Setting`` model is present
without pinning a tenant-specific cis migration number.
"""
import json

from django.db import migrations

MENU_SETTING_KEY = 'cis.settings.menu'

ETHOS_GROUP_NAME = 'ethos'

SETTINGS_ITEM = {
    'label': 'Settings',
    'name': 'ethos_settings',
    'url': 'ethos:ethos_settings',
}


def _load_ce_menu(value):
    raw = value.get('ce_menu')
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _ethos_group(items):
    for item in items:
        if item.get('name') == ETHOS_GROUP_NAME:
            return item
    return None


def add_settings_item(apps, schema_editor):
    Setting = apps.get_model('cis', 'Setting')
    try:
        setting = Setting.objects.get(key=MENU_SETTING_KEY)
    except Setting.DoesNotExist:
        return

    value = setting.value or {}
    items = _load_ce_menu(value)
    if items is None:
        return

    group = _ethos_group(items)
    if group is None:
        return

    sub_menu = group.setdefault('sub_menu', [])
    if any(sub.get('name') == SETTINGS_ITEM['name'] for sub in sub_menu):
        return

    sub_menu.append(dict(SETTINGS_ITEM))

    value['ce_menu'] = json.dumps(items)
    setting.value = value
    setting.save()


def remove_settings_item(apps, schema_editor):
    Setting = apps.get_model('cis', 'Setting')
    try:
        setting = Setting.objects.get(key=MENU_SETTING_KEY)
    except Setting.DoesNotExist:
        return

    value = setting.value or {}
    items = _load_ce_menu(value)
    if items is None:
        return

    group = _ethos_group(items)
    if group is None:
        return

    sub_menu = group.get('sub_menu', [])
    pruned = [sub for sub in sub_menu
              if sub.get('name') != SETTINGS_ITEM['name']]
    if len(pruned) == len(sub_menu):
        return

    group['sub_menu'] = pruned
    value['ce_menu'] = json.dumps(items)
    setting.value = value
    setting.save()


class Migration(migrations.Migration):

    dependencies = [
        ('ethos', '0007_ethosmessage_sis_message_id_text'),
        ('cis', '__first__'),
    ]

    operations = [
        migrations.RunPython(add_settings_item, remove_settings_item),
    ]

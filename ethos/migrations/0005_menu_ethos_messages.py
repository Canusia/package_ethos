"""Add the "Messages" sub-item to the CE sidebar's SIS nav group.

The portal menus are pulled (by ``cis.menu.draw_menu``) from the DB-backed
``cis.settings.menu`` Setting, keyed ``<role>_menu`` — each one a JSON *string*.
Editing the hardcoded lists in ``cis/menu.py`` does nothing; the DB row is the
source of truth. This data migration makes ``/ce/ethos/messages/`` reachable
without hand-editing JSON in the settings UI.

Only ``ce_menu`` is touched: the messages pages are CE-role gated
(``ethos/urls.py`` wraps each route in ``user_passes_test(_has_cis_role)``), so
no other role's menu should advertise them.

If the SIS group (``name == 'ethos'``) is absent, this no-ops rather than
creating it. A tenant that has not added the SIS nav group would otherwise get
an orphan group holding only "Messages" and none of Resources/Logs/Status —
README section 6 remains the path for that initial setup.

Idempotent: re-running makes no further changes. No-ops if the menu Setting row
doesn't exist yet (e.g. before ``register_settings`` has run on a fresh
install). Depends on cis ``__first__`` so the ``Setting`` model is present
without pinning a tenant-specific cis migration number.
"""
import json

from django.db import migrations

MENU_SETTING_KEY = 'cis.settings.menu'

ETHOS_GROUP_NAME = 'ethos'
LOGS_ITEM_NAME = 'ethos_logs'

MESSAGES_ITEM = {
    'label': 'Messages',
    'name': 'ethos_messages',
    'url': 'ethos:ethos_messages',
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


def add_messages_item(apps, schema_editor):
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
    if any(sub.get('name') == MESSAGES_ITEM['name'] for sub in sub_menu):
        return

    # Sit next to "All Logs" — Messages is the log-adjacent screen. Falls back
    # to the end of the group if that item has been renamed or removed.
    idx = next(
        (n + 1 for n, sub in enumerate(sub_menu)
         if sub.get('name') == LOGS_ITEM_NAME),
        len(sub_menu),
    )
    sub_menu.insert(idx, dict(MESSAGES_ITEM))

    value['ce_menu'] = json.dumps(items)
    setting.value = value
    setting.save()


def remove_messages_item(apps, schema_editor):
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
              if sub.get('name') != MESSAGES_ITEM['name']]
    if len(pruned) == len(sub_menu):
        return

    group['sub_menu'] = pruned
    value['ce_menu'] = json.dumps(items)
    setting.value = value
    setting.save()


class Migration(migrations.Migration):

    dependencies = [
        ('ethos', '0004_ethosconsumecursor_ethosmessage'),
        ('cis', '__first__'),
    ]

    operations = [
        migrations.RunPython(add_messages_item, remove_messages_item),
    ]

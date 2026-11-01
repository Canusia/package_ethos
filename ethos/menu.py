"""The ce "SIS" sidebar section (cis.menu_registry).

Ids are the legacy names added by the ethos menu migrations. The section sits
after Staff (140). On a cis without the registry nothing registers.
"""
try:
    from cis.menu_registry import menu
except ImportError:   # cis without the registry: the menu migrations still apply
    menu = None

if menu is not None:
    menu.section('ce', 'ethos', 'SIS', 'fas fa-fw fa-user', order=145)
    for _id, _label, _order in [
        ('ethos_resources', 'All Resources', 10),
        ('ethos_logs', 'All Logs', 20),
        ('ethos_messages', 'Messages', 30),
        ('ethos_status', 'Status', 40),
        ('ethos_settings', 'Settings', 50),
    ]:
        menu.register('ce', _id, _label, url='ethos:' + _id, parent='ethos',
                      order=_order)

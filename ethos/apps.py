from django.apps import AppConfig

# Shared body of the settings-configurator entry. The 'app' key is NOT included
# here on purpose: it differs between the two configs below, because the dotted
# app path differs between pip-installed and submodule modes. A stale 'app'
# value is enough to 500 the settings-detail page, so each config states its own.
_CONSUME_CONFIGURATOR = {
    'name': 'ethos_consume',
    'title': 'Ethos Change Notifications',
    'description': 'Polling schedule and batch sizes for inbound SIS change notifications.',
    'categories': [
        '3'
    ],
}


class EthosConfig(AppConfig):
    """Production — pip-installed package."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ethos'

    CONFIGURATORS = [
        {'app': 'ethos', **_CONSUME_CONFIGURATOR},
    ]


class DevEthosConfig(AppConfig):
    """Development — git submodule."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ethos.ethos'

    CONFIGURATORS = [
        {'app': 'ethos.ethos', **_CONSUME_CONFIGURATOR},
    ]

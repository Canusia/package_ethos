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

_GRADE_PUSH_CONFIGURATOR = {
    'name': 'grade_push',
    'title': 'Banner Grade Push',
    'description': 'Banner GUIDs sent with final grades: grade type, grade map and submitted-by. '
                   'Stored in SIS GUIDS.',
    'categories': ['3'],
}

# Report manifest for register_reports; 'app' is added per config, as above.
_GRADE_COMPARISON_REPORT = {
    'name': 'banner_grade_comparison',
    'title': 'Banner vs MyCE Grades',
    'description': 'Grade and registration status of each registration in Banner and in MyCE, '
                   'for one or more terms. Reads Banner class by class.',
    'categories': ['Classes'],
    'available_for': ['ce'],
}


class EthosConfig(AppConfig):
    """Production — pip-installed package."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ethos'

    CONFIGURATORS = [
        {'app': 'ethos', **_CONSUME_CONFIGURATOR},
        {'app': 'ethos', **_GRADE_PUSH_CONFIGURATOR},
    ]

    REPORTS = [{'app': 'ethos', **_GRADE_COMPARISON_REPORT}]


class DevEthosConfig(AppConfig):
    """Development — git submodule."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ethos.ethos'

    CONFIGURATORS = [
        {'app': 'ethos.ethos', **_CONSUME_CONFIGURATOR},
        {'app': 'ethos.ethos', **_GRADE_PUSH_CONFIGURATOR},
    ]

    REPORTS = [{'app': 'ethos.ethos', **_GRADE_COMPARISON_REPORT}]

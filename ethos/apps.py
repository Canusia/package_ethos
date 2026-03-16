from django.apps import AppConfig


class EthosConfig(AppConfig):
    """Production — pip-installed package."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ethos'


class DevEthosConfig(AppConfig):
    """Development — git submodule."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ethos.ethos'

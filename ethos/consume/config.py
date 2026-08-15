"""Consume-pipeline configuration.

Values arrive as SECRETS -> a module-level name in the host settings.py ->
getattr here. Every key has a working default so a tenant that configures
nothing still functions.
"""

from django.conf import settings


def consume_limit():
    """Max notifications per /consume call. Ethos allows 1-1000."""
    return getattr(settings, 'ETHOS_CONSUME_LIMIT', 100)


def retention_days():
    """Days of EthosMessage history to keep."""
    return getattr(settings, 'ETHOS_CONSUME_RETENTION_DAYS', 30)


def log_retention_days():
    """Days of EthosLog history to keep."""
    return getattr(settings, 'ETHOS_LOG_RETENTION_DAYS', 90)


def handler_paths():
    """{resource_name: 'dotted.path.To.Handler'} — tenant-owned."""
    return getattr(settings, 'ETHOS_CONSUME_HANDLERS', {}) or {}


def auto_consume_enabled(resource_name):
    """Whether the poller's messages for this resource may consume unattended.

    Off for every resource by default: consuming is opt-in per resource type.
    """
    return bool((getattr(settings, 'ETHOS_CONSUME_AUTO', {}) or {}).get(resource_name, False))

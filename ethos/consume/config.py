"""Consume-pipeline configuration.

Two tiers, deliberately:

**Operator-tunable** — poll on/off, notifications per request, batches per run,
and whether a scheduled run also consumes. These live in the DB-backed
``ethos.settings.ethos_consume`` Setting, editable at ``/ce/settings/``. The
Setting wins when it holds a usable value; the Django-settings key below is the
fallback for a fresh install where ``register_settings`` has not run yet.

**Deployment-level** — retention windows, the per-resource auto-consume map,
and the handler registry. These stay as SECRETS -> a module-level name in the
host settings.py -> getattr here, because they are not things a CE admin should
change from a web form: retention governs data destruction, and the auto-consume
map plus handler registry decide what mutates student records.

Every key has a working default, so a tenant that configures nothing still runs.
"""

from django.conf import settings


def _consume_setting():
    """The operator Setting class, imported lazily.

    Deferred because this module is imported from the poller and the management
    commands, and the Setting class reaches into ``cis`` models — importing it at
    module scope would make ``cis`` a load-time dependency of the consume package.
    """
    from ..settings.ethos_consume import ethos_consume
    return ethos_consume


def poll_enabled():
    """Master switch. When False the scheduled job exits without calling Ethos."""
    return _consume_setting().is_poll_enabled()


def consume_after_poll():
    """Whether a scheduled run also dispatches what it just stored.

    Note this is necessary but not sufficient: each resource type must ALSO be
    enabled in ``auto_consume_enabled`` below, so turning this on does not by
    itself start mutating records.
    """
    return _consume_setting().consume_after_poll_enabled()


def consume_limit():
    """Max notifications per /consume call. Ethos allows 1-1000."""
    configured = _consume_setting().get_limit()
    if configured is not None:
        return configured
    return getattr(settings, 'ETHOS_CONSUME_LIMIT', 100)


def max_batches():
    """How many /consume requests one scheduled run may make."""
    configured = _consume_setting().get_max_batches()
    if configured is not None:
        return configured
    return getattr(settings, 'ETHOS_CONSUME_MAX_BATCHES', 1)


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

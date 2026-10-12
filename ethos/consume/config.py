"""Consume-pipeline configuration.

Two tiers, deliberately:

**Operator-tunable** — poll on/off, notifications per request, batches per run,
and whether a scheduled run also consumes. These live in the DB-backed
``ethos.settings.ethos_consume`` Setting, editable at ``/ce/settings/``. The
Setting wins when it holds a usable value; the Django-settings key below is the
fallback for a fresh install where ``register_settings`` has not run yet.

**Deployment-level** — retention windows, the per-resource auto-consume map,
and the handler registry. These are read from the host settings.py via getattr
here, because they are not things a CE admin should change from a web form:
retention governs data destruction, and the auto-consume map plus handler
registry decide what mutates student records.

The split for turning consuming on (package_ethos#6):

- ``ETHOS_CONSUME_AUTO`` is a **code allowlist**. Set it in ``settings.py`` next
  to ``ETHOS_CONSUME_HANDLERS``, never in SECRETS, and add a resource only once
  its handler has been reviewed. It is the upper bound on what may mutate
  records unattended.
- **"Consume After Polling"** on the Setting is the **switch** staff use, with no
  deploy. The Setting form lists each handled resource and whether the allowlist
  admits it (``handled_resources`` below), so "Yes" is not a guess.

Putting the map in SECRETS makes enabling a resource a Secrets Manager edit plus
a pod restart, which is worse than either a reviewed code change or the Setting.

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

    Off for every resource by default: consuming is opt-in per resource type, via
    the ``ETHOS_CONSUME_AUTO`` code allowlist in the host's settings.py.
    """
    return bool((getattr(settings, 'ETHOS_CONSUME_AUTO', {}) or {}).get(resource_name, False))


def handled_resources():
    """[(resource_name, allowed)] for every resource with a configured handler, sorted.

    ``allowed`` is whether ``ETHOS_CONSUME_AUTO`` lets it consume unattended. A
    resource in the allowlist without a handler is not listed: nothing would run.
    """
    return [(name, auto_consume_enabled(name)) for name in sorted(handler_paths())]

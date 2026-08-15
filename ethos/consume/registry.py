"""Resolve a consume handler for a resource name.

Handlers are configured by dotted path in settings, so the tenant owns the
policy and adding a resource type later is a settings entry plus a class -- no
framework change:

    ETHOS_CONSUME_HANDLERS = {
        'section-registrations':
            'myce_tenant_configs.services.ethos_consume.SectionRegistrationHandler',
    }
"""

from django.utils.module_loading import import_string

from . import config


def get_handler(resource_name):
    """Return a handler instance for the resource, or None if none configured.

    Raises ImportError if a path is configured but cannot be imported — a
    misconfiguration should be loud, not silently treated as "no handler".
    """
    path = config.handler_paths().get(resource_name)
    if not path:
        return None
    return import_string(path)()

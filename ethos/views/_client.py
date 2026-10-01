"""Build an Ethos client for a CE view without ever raising to a 500 (package_ethos#4)."""
import logging

from ..credentials import EthosNotConfigured

logger = logging.getLogger(__name__)

NOT_CONFIGURED_MESSAGE = 'Ethos is not configured for this campus.'


def ethos_client_or_error(request=None, factory=None, campus=None):
    """Return (client, None), or (None, message) when the campus has no Ethos credentials
    (or, in multi-campus mode, no campus context to pick them from). `factory` lets a
    caller pass its own module-level Ethos so existing patch points keep working.
    `campus` is the campus of the record the view acts on; None means the ambient one."""
    from cis.campus_context import NoCampusContext
    if factory is None:
        from ..library.ethos import Ethos as factory
    try:
        if campus is None:
            return factory(), None
        return factory(campus=campus), None
    except (EthosNotConfigured, NoCampusContext):
        return None, NOT_CONFIGURED_MESSAGE

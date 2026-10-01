"""Base class for Ethos management commands (package_ethos#4).

Not a command module: it lives beside commands/ so Django never tries to run it.
"""
from django.core.management.base import CommandError

from cis.campus_context import NoCampusContext
from cis.management.campus_command import CampusCommand

from .consume.poller import CursorNotInitialised
from .credentials import EthosNotConfigured


class EthosCommand(CampusCommand):
    """CampusCommand that reports a missing campus, credentials or queue cursor as a
    CommandError rather than a traceback."""

    def execute(self, *args, **options):
        try:
            return super().execute(*args, **options)
        except (EthosNotConfigured, NoCampusContext, CursorNotInitialised) as exc:
            raise CommandError(str(exc))

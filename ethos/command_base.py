"""Base class for Ethos management commands (package_ethos#4).

Not a command module: it lives beside commands/ so Django never tries to run it.
"""
from django.core.management.base import CommandError

from cis.campus_context import NoCampusContext
from cis.management.campus_command import CampusCommand

from .credentials import EthosNotConfigured


class EthosCommand(CampusCommand):
    """CampusCommand that reports a missing campus or credentials as a CommandError."""

    def execute(self, *args, **options):
        try:
            return super().execute(*args, **options)
        except (EthosNotConfigured, NoCampusContext) as exc:
            raise CommandError(str(exc))

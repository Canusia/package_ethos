import logging

from ...command_base import EthosCommand
from ...library.ethos import Ethos
from ...views.resources import sync_resources

logger = logging.getLogger(__name__)


class Command(EthosCommand):
    """Sync available Ethos resources/applications to the local database."""
    help = 'Fetch GET /admin/available-resources from Ethos and upsert into EthosApplication/Resource/Representation tables.'

    def handle(self, *args, **kwargs):
        ethos = Ethos()
        self.stdout.write('Fetching available resources from Ethos...')
        apps_data = ethos.get_available_resources()

        if not apps_data:
            self.stdout.write(self.style.ERROR('No data returned — check API credentials or connectivity.'))
            return

        apps_synced, resources_synced = sync_resources(apps_data, campus=ethos.campus)
        self.stdout.write(self.style.SUCCESS(
            f'Synced {apps_synced} application(s) and {resources_synced} resource(s).'
        ))

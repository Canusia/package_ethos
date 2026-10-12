"""Fill the SIS GUIDS blob from Ethos code tables (package_ethos#3).

The payload builders read race, ethnicity, phone, email, address and emergency-contact
type GUIDs from the ``guids`` JSON in the cis "SIS GUIDS" setting, and send null for any key
that is unset. This command reads the tenant's own code tables and writes the keys it can
resolve. A key that already holds a value is kept unless ``--overwrite`` is passed, and
every other key in the blob, and every other field on the setting, is left alone.

    python manage.py populate_sis_guids --dry-run
    python manage.py populate_sis_guids
    python manage.py populate_sis_guids --overwrite
    python manage.py populate_sis_guids --only races,ethnicities

SIS GUIDS is one row per campus on a multi-campus deployment: pass ``--campus <code>``.
"""
import json

from django.core.management.base import CommandError

from cis.campus_context import current_campus, is_multi_campus
from cis.models.settings import Setting, is_campus_scoped
from cis.settings.sis_settings import sis_settings

from ...client import get_client
from ...command_base import EthosCommand
from ...reference import RESOURCES, build_guid_map, merge_guids


class Command(EthosCommand):
    help = ('Read race, ethnicity, phone, email, address and emergency-contact type GUIDs '
            'from Ethos into SIS GUIDS.')

    def add_arguments(self, parser):
        super().add_arguments(parser)  # --campus
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would change without writing.')
        parser.add_argument('--overwrite', action='store_true',
                            help='Replace keys that already hold a value. Off by default so a '
                                 'hand-set GUID is not replaced by the preferred-code guess.')
        parser.add_argument('--only', default='',
                            help=f'Comma-separated subset of: {", ".join(RESOURCES)}')

    def handle(self, *args, **options):
        only = {r.strip() for r in options['only'].split(',') if r.strip()}
        unknown = only - set(RESOURCES)
        if unknown:
            raise CommandError(f'Unknown resource(s): {", ".join(sorted(unknown))}. '
                               f'Valid: {", ".join(RESOURCES)}')

        # Read the blob first: a corrupt one stops the command before any Ethos call.
        setting = Setting.objects.filter(key=sis_settings.key).first()
        value = dict(setting.value or {}) if setting else {}
        existing = self._parse_blob(value.get('guids'))

        fetched, report = build_guid_map(get_client(), only=only or None)
        self._print_report(report)

        if not fetched:
            self.stdout.write(self.style.WARNING('\nNothing resolved. SIS GUIDS was not touched.'))
            return

        merged, changed, skipped = merge_guids(existing, fetched, overwrite=options['overwrite'])

        self.stdout.write('')
        for key in changed:
            self.stdout.write(self.style.SUCCESS(f'  set     {key}'))
        for key in skipped:
            self.stdout.write(self.style.WARNING(f'  kept    {key} (already set; --overwrite to replace)'))

        if not changed:
            self.stdout.write('\nNo keys to write.')
            return

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f'\nDry run: {len(changed)} key(s) not written.'))
            return

        value['guids'] = json.dumps(merged, indent=2)
        if setting is None:
            setting = Setting(key=sis_settings.key)
            if is_multi_campus() and is_campus_scoped(sis_settings.key):
                setting.campus = current_campus()
        setting.value = value
        setting.save()
        self.stdout.write(self.style.SUCCESS(f'\nWrote {len(changed)} key(s) to SIS GUIDS.'))

    @staticmethod
    def _parse_blob(raw):
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            blob = json.loads(raw)
        except ValueError as exc:
            raise CommandError(f'SIS GUIDS is not valid JSON ({exc}); fix it on the settings '
                               'page first. Nothing was changed.')
        if not isinstance(blob, dict):
            raise CommandError('SIS GUIDS is not a JSON object; nothing was changed.')
        return blob

    def _print_report(self, report):
        styles = {
            'ok': self.style.SUCCESS,
            'partial': self.style.WARNING,
            'unmatched': self.style.WARNING,
            'empty': self.style.WARNING,
            'error': self.style.ERROR,
        }
        for entry in report:
            style = styles.get(entry['status'], self.style.NOTICE)
            self.stdout.write(style(f"{entry['resource']:<22} {entry['status']:<10} {entry['detail']}"))
            # Show the available codes for anything that did not resolve cleanly:
            # picking the right one is a CE decision.
            if entry['status'] in ('unmatched', 'partial') and entry.get('options'):
                self.stdout.write(f"{'':<23}options: {', '.join(entry['options'][:20])}")

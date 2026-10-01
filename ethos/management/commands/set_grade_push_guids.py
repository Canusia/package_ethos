"""Write the final-grade push keys into the SIS GUIDS setting.

The grade push (``grade_push.push_final_grade``) reads three keys from the
``sis_guids`` JSON blob held in the cis "SIS GUIDS" setting:

    final_grade_type    {"id": guid}            required
    grade_map           {"<MyCE grade>": guid}  required
    grade_submitted_by  {"id": guid}            optional

The blob is shared with every other Ethos lookup, so this command edits only
those three keys and leaves the rest of the blob, and any other field on the
setting, as they were. The save goes through the Setting model, so it lands in
the setting's history like an edit made on the settings page.

    python manage.py set_grade_push_guids --final-grade-type <guid> \\
        --grade A=<guid> --grade B=<guid> --dry-run
    python manage.py set_grade_push_guids --grade-map-file grades.json
"""
import json
import uuid

from django.core.management.base import BaseCommand, CommandError

from cis.models.settings import Setting
from cis.settings.sis_settings import sis_settings

from ...grade_push import config_errors


def _guid(value, label):
    try:
        return str(uuid.UUID(str(value).strip()))
    except ValueError:
        raise CommandError(f'{label}: {value!r} is not a GUID.')


def _grade_pair(arg):
    grade, sep, guid = arg.partition('=')
    if not sep or not grade.strip():
        raise CommandError(f'--grade {arg!r}: expected GRADE=GUID, e.g. A=<guid>.')
    return grade.strip(), _guid(guid, f'--grade {grade.strip()}')


class Command(BaseCommand):
    help = 'Set the final-grade push keys (final_grade_type, grade_map, grade_submitted_by) in SIS GUIDS.'

    def add_arguments(self, parser):
        parser.add_argument('--final-grade-type', metavar='GUID',
                            help='Banner GUID of the FINAL grade type.')
        parser.add_argument('--grade', action='append', default=[], metavar='GRADE=GUID',
                            help='One grade_map entry. Repeatable.')
        parser.add_argument('--grade-map-file', metavar='PATH',
                            help='JSON file of {"<MyCE grade>": "<guid>"} entries.')
        parser.add_argument('--replace-grade-map', action='store_true',
                            help='Replace the existing grade_map instead of merging into it.')
        who = parser.add_mutually_exclusive_group()
        who.add_argument('--submitted-by', metavar='GUID',
                         help='Banner person GUID sent as submittedBy.')
        who.add_argument('--clear-submitted-by', action='store_true',
                         help='Remove grade_submitted_by, so submittedBy is omitted.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show the result without saving.')

    def handle(self, *args, **options):
        grades = dict(_grade_pair(a) for a in options['grade'])
        if options['grade_map_file']:
            grades.update(self._read_map_file(options['grade_map_file']))

        changes = {}
        if options['final_grade_type']:
            changes['final_grade_type'] = {
                'id': _guid(options['final_grade_type'], '--final-grade-type')}
        if options['submitted_by']:
            changes['grade_submitted_by'] = {
                'id': _guid(options['submitted_by'], '--submitted-by')}
        if not (changes or grades or options['clear_submitted_by']
                or options['replace_grade_map']):
            raise CommandError('Nothing to apply. See --help.')

        setting = Setting.objects.filter(key=sis_settings.key).first()
        value = dict(setting.value) if setting else {}
        before = self._parse_blob(value.get('guids'))

        after = dict(before)
        after.update(changes)
        if grades or options['replace_grade_map']:
            base = {} if options['replace_grade_map'] else dict(before.get('grade_map') or {})
            base.update(grades)
            after['grade_map'] = base
        if options['clear_submitted_by']:
            after.pop('grade_submitted_by', None)

        self._report(before, after)
        for error in config_errors(after):
            self.stdout.write(self.style.WARNING(f'Still missing: {error}'))

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('Dry run: nothing saved.'))
            return

        value['guids'] = json.dumps(after, indent=2)
        if setting is None:
            setting = Setting(key=sis_settings.key)
        setting.value = value
        setting.save()
        self.stdout.write(self.style.SUCCESS('Saved SIS GUIDS.'))

    def _read_map_file(self, path):
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, ValueError) as exc:
            raise CommandError(f'--grade-map-file {path}: {exc}')
        if not isinstance(data, dict):
            raise CommandError(f'--grade-map-file {path}: expected a JSON object.')
        return {str(k).strip(): _guid(v, f'{path} {k}') for k, v in data.items()}

    @staticmethod
    def _parse_blob(raw):
        if not raw:
            return {}
        try:
            blob = json.loads(raw)
        except ValueError as exc:
            raise CommandError(
                f'SIS GUIDS is not valid JSON ({exc}); fix it on the settings page '
                'first. Nothing was changed.')
        if not isinstance(blob, dict):
            raise CommandError('SIS GUIDS is not a JSON object; nothing was changed.')
        return blob

    def _report(self, before, after):
        for key in ('final_grade_type', 'grade_map', 'grade_submitted_by'):
            old, new = before.get(key), after.get(key)
            mark = '  ' if old == new else '* '
            self.stdout.write(f'{mark}{key}:')
            self.stdout.write(f'    before: {json.dumps(old, sort_keys=True)}')
            self.stdout.write(f'    after:  {json.dumps(new, sort_keys=True)}')

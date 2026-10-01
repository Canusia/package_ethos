"""Give a campus the Ethos rows that predate multi-campus (package_ethos #4).

Run once when a single-campus tenant turns MULTI_CAMPUS on: the consume
cursor, applications, messages and call logs all still have campus NULL, and
in multi-campus mode a poll for a campus finds no cursor of its own. This
assigns the NULL rows to the campus that has been using them. Rows already on
a campus are never touched.

    python manage.py assign_ethos_campus --campus EWU --dry-run
    python manage.py assign_ethos_campus --campus EWU

Works in both modes; it names its campus explicitly.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...models import EthosApplication, EthosConsumeCursor, EthosLog, EthosMessage


class Command(BaseCommand):
    help = 'Assign the campus-less Ethos cursor, applications, messages and logs to one campus.'

    def add_arguments(self, parser):
        parser.add_argument('--campus', required=True, help='Campus code.')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--batch-size', type=int, default=5000)

    def handle(self, *args, **options):
        from cis.models.course import Campus

        try:
            campus = Campus.objects.get(code=options['campus'])
        except Campus.DoesNotExist:
            raise CommandError(f"No campus with code {options['campus']!r}.")
        dry = options['dry_run']
        size = max(1, options['batch_size'])
        verb = 'would move' if dry else 'moved'

        for model in (EthosMessage, EthosLog):
            total = self._assign_batched(model, campus, size, dry)
            self.stdout.write(f'{model.__name__}: {total} {verb} to {campus.code}.')

        # Applications and the cursor go together, cursor last: moving the cursor
        # lets poll start creating (campus, ethos_id) rows, which must not race
        # the applications update.
        null_cursors = list(EthosConsumeCursor.objects.filter(campus__isnull=True).order_by('pk'))
        blocked = bool(null_cursors) and EthosConsumeCursor.objects.filter(campus=campus).exists()
        with transaction.atomic():
            self._assign_applications(campus, verb, dry)
            if blocked:
                n_cursor = 0
            else:
                # The oldest null row (the one load(None) used) becomes the campus's.
                # Extra null rows stay put, as campus is unique on the cursor.
                n_cursor = len(null_cursors[:1])
                if n_cursor and not dry:
                    EthosConsumeCursor.objects.filter(pk=null_cursors[0].pk).update(campus=campus)
        self.stdout.write(f'EthosConsumeCursor: {n_cursor} {verb} to {campus.code}.')
        if len(null_cursors) > 1 and not blocked:
            self.stdout.write(f'  skipped {len(null_cursors) - 1} extra campus-less cursor row(s).')
        if blocked:
            raise CommandError(
                f'Cursor NOT assigned: {campus.code} already has a consume cursor and a '
                'campus-less cursor also exists. Merging them would lose a queue position; '
                'delete or reconcile one by hand, then re-run. Everything else was assigned.')

    def _assign_applications(self, campus, verb, dry):
        # (campus, ethos_id) is unique, so skip ids the campus already has.
        have = set(EthosApplication.objects.filter(campus=campus).values_list('ethos_id', flat=True))
        apps = list(EthosApplication.objects.filter(campus__isnull=True).values_list('pk', 'ethos_id'))
        movable = [pk for pk, eid in apps if eid not in have]
        clashes = [eid for pk, eid in apps if eid in have]
        if not dry:
            EthosApplication.objects.filter(pk__in=movable).update(campus=campus)
        self.stdout.write(f'EthosApplication: {len(movable)} {verb} to {campus.code}.')
        for eid in clashes:
            self.stdout.write(f'  skipped application {eid}: {campus.code} already has it.')

    def _assign_batched(self, model, campus, size, dry):
        qs = model.objects.filter(campus__isnull=True)
        if dry:
            return qs.count()
        total = 0
        while True:
            pks = list(qs.order_by('pk').values_list('pk', flat=True)[:size])
            if not pks:
                return total
            total += model.objects.filter(pk__in=pks, campus__isnull=True).update(campus=campus)

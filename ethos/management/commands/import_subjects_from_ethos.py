import logging

from django.core.management.base import BaseCommand

from ...library.ethos import Ethos

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    '''Import subjects from Ethos into the local Cohort table.'''
    help = 'Fetch subjects from the Ethos API and optionally create/update Cohort records.'

    def add_arguments(self, parser):
        parser.add_argument('--create', action='store_true', help='Create/update subjects in local database')

    def handle(self, *args, **kwargs):
        ethos = Ethos()
        subjects = ethos.get_subjects()

        self.stdout.write(f'Found {len(subjects)} subjects in Ethos.')
        for subject in subjects:
            self.stdout.write(f"  {subject.get('abbreviation')}  {subject.get('title')}  {subject.get('id')}")

        if not kwargs['create']:
            self.stdout.write(self.style.NOTICE('Dry run — pass --create to import into the database.'))
            return

        from cis.models.course import Cohort

        created = 0
        updated = 0
        for subject in subjects:
            abbreviation = subject.get('abbreviation', '')
            title = subject.get('title', abbreviation)
            ethos_id = subject.get('id', '')

            cohort, was_created = Cohort.objects.get_or_create(
                designator=abbreviation,
                defaults={'name': title},
            )

            changed = False
            if ethos_id and not cohort.external_sis_id:
                cohort.external_sis_id = ethos_id
                changed = True
            if cohort.meta != subject:
                cohort.meta = subject
                changed = True

            if changed:
                cohort.save()

            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'Synced {len(subjects)} subject(s): {created} created, {updated} existing.'))

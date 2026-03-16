import logging

from django.core.management.base import BaseCommand

from ...library.ethos import Ethos

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    '''Import courses from Ethos into the local Course table.'''
    help = 'Fetch courses from the Ethos API and optionally create/update Course records.'

    def add_arguments(self, parser):
        parser.add_argument('--create', action='store_true', help='Create/update courses in local database')

    def handle(self, *args, **kwargs):
        ethos = Ethos()
        courses = ethos.get_courses()

        self.stdout.write(f'Found {len(courses)} courses in Ethos.')
        for course in courses:
            subject = course.get('subject', {})
            self.stdout.write(
                f"  {subject.get('abbreviation', '')}{course.get('number', '')}  "
                f"{course.get('title', '')}  {course.get('id', '')}"
            )

        if not kwargs['create']:
            self.stdout.write(self.style.NOTICE('Dry run — pass --create to import into the database.'))
            return

        from cis.models.course import Cohort, Course

        created = 0
        skipped = 0
        updated = 0

        for course_data in courses:
            subject = course_data.get('subject', {})
            subject_id = subject.get('id', '')
            number = course_data.get('number', '')
            title = course_data.get('title', '')
            ethos_id = course_data.get('id', '')

            if not subject_id or not number:
                self.stdout.write(self.style.WARNING(
                    f'  Skipping course — missing subject id or number: {course_data}'
                ))
                skipped += 1
                continue

            # Look up cohort by the subject's Ethos GUID
            try:
                cohort = Cohort.objects.get(external_sis_id=subject_id)
            except Cohort.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"  Skipping — no Cohort found for subject id {subject_id} "
                    f"({subject.get('abbreviation', '')})"
                ))
                skipped += 1
                continue

            name = f"{cohort.designator} {number}"

            course, was_created = Course.objects.get_or_create(
                cohort=cohort,
                catalog_number=number,
                campus=None,
                credit_hours=course_data.get('credits', [{'minimum': 0}])[0].get('minimum', 0) if course_data.get('credits') else '99',
                defaults={
                    'name': name,
                    'title': title,
                    'status': 'Inactive',
                    'external_sis_id': ethos_id,
                    'meta': course_data,
                },
            )

            if was_created:
                created += 1
            else:
                changed = False
                if ethos_id and not course.external_sis_id:
                    course.external_sis_id = ethos_id
                    changed = True
                if course.meta != course_data:
                    course.meta = course_data
                    changed = True
                if changed:
                    course.save()
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Synced {len(courses)} course(s): {created} created, {updated} existing, {skipped} skipped.'
        ))

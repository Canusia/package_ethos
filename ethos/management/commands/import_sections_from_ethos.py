import csv
import logging

from django.core.management.base import BaseCommand

from ...library.ethos import Ethos

logger = logging.getLogger(__name__)

UUID_LENGTH = 36


def _is_uuid(value):
    return len(value) == UUID_LENGTH and value.count('-') == 4


class Command(BaseCommand):
    '''Fetch sections from Ethos for a term and upsert them into the CIS database.'''
    help = 'Fetch sections from the Ethos API for a given term and optionally create/update records.'

    def add_arguments(self, parser):
        parser.add_argument(
            'term',
            help='Term code (e.g. "202620") or academic period GUID',
        )
        parser.add_argument(
            '--create',
            action='store_true',
            help='Write to the database (default is dry-run)',
        )
        parser.add_argument(
            '--no-certificates',
            action='store_true',
            dest='no_certificates',
            help='Skip creating TeacherCourseCertificate records',
        )
        parser.add_argument(
            '--csv',
            dest='csv_path',
            metavar='FILE',
            help='Save sections to a CSV file at the given path',
        )

    def handle(self, *args, **options):
        term_arg = options['term']
        do_create = options['create']
        skip_certificates = options['no_certificates']
        csv_path = options.get('csv_path')

        ethos = Ethos()

        # Resolve period GUID
        if _is_uuid(term_arg):
            period_id = term_arg
            self.stdout.write(f'Using period GUID directly: {period_id}')
        else:
            self.stdout.write(f'Looking up academic period for term code: {term_arg}')
            period_id = ethos.get_academic_period_id(term_arg)
            if not period_id:
                self.stdout.write(self.style.ERROR(f'Could not resolve period GUID for term code: {term_arg}'))
                return
            self.stdout.write(f'Resolved period GUID: {period_id}')

        from cis.models.term import Term
        term = Term.objects.filter(external_sis_id=period_id).first()
        if not term and not _is_uuid(term_arg):
            term = Term.objects.filter(code=term_arg).first()
        if not term:
            self.stdout.write(self.style.ERROR(
                f'No Term found in DB with external_sis_id={period_id}. '
                f'Create the term first or run import_terms_from_ethos.'
            ))
            return
        self.stdout.write(f'Using term: {term} (id={term.pk})')

        self.stdout.write('Fetching sections from Ethos...')
        raw_sections = ethos.get_sections(period_id=period_id)
        self.stdout.write(f'Found {len(raw_sections)} sections.')

        if csv_path:
            self._write_csv(raw_sections, csv_path)

        if not do_create:
            self._dry_run(raw_sections)
            self.stdout.write(self.style.NOTICE('Dry run — pass --create to import into the database.'))
            return

        self._import(raw_sections, skip_certificates, term)

    def _dry_run(self, raw_sections):
        for section in raw_sections:
            code = section.get('code', '?')
            course_data = section.get('course', {})
            subject = course_data.get('subject', {}).get('abbreviation', '?')
            catalog = course_data.get('number', '?')
            number = section.get('number', '?')

            roster = section.get('instructorRosterDetails', [])
            primary = next(
                (r for r in roster if r.get('instructorRole') == 'primary'),
                roster[0] if roster else None,
            )
            instructor_name = ''
            if primary:
                names = primary.get('instructor', {}).get('names', [{}])
                instructor_name = f"{names[0].get('firstName', '')} {names[0].get('lastName', '')}".strip()

            try:
                building_code = section['instructionalEvents'][0]['locations'][0]['location']['building']['code']
            except (KeyError, IndexError):
                building_code = None

            self.stdout.write(
                f'  CRN {code} | {subject} {catalog} sec {number} | '
                f'building={building_code or "-"} | instructor={instructor_name or "-"}'
            )

    def _write_csv(self, raw_sections, path):
        from django.db.models import Q
        from cis.models.term import Term
        from cis.models.course import Cohort, Course
        from cis.models.highschool import HighSchool
        from cis.models.teacher import Teacher

        fieldnames = [
            'id', 'course_name', 'highschool', 'section_number',
            'class_number', 'term_name', 'term_code',
            'instructor_name', 'instructor_email',
            'term_status', 'course_status', 'highschool_status', 'teacher_status',
        ]

        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for section in raw_sections:
                course_data = section.get('course', {})
                subject_abbr = course_data.get('subject', {}).get('abbreviation', '')
                catalog_num = course_data.get('number', '')
                course_name = f'{subject_abbr} {catalog_num}'.strip()

                try:
                    building_code = section['instructionalEvents'][0]['locations'][0]['location']['building']['code']
                except (KeyError, IndexError):
                    building_code = ''

                schedule_period = section.get('scheduleAcademicPeriod', {})

                roster = section.get('instructorRosterDetails', [])
                primary = next(
                    (r for r in roster if r.get('instructorRole') == 'primary'),
                    roster[0] if roster else None,
                )
                instructor_name, instructor_email = '', ''
                if primary:
                    instructor = primary.get('instructor', {})
                    names = instructor.get('names', [{}])
                    first = names[0].get('firstName', '') if names else ''
                    last = names[0].get('lastName', '') if names else ''
                    instructor_name = f'{first} {last}'.strip()
                    credentials = instructor.get('credentials', [])
                    banner_username = next(
                        (c['value'] for c in credentials if c.get('type') == 'bannerUserName'), ''
                    )
                    if banner_username:
                        instructor_email = banner_username + '@ewu.edu'

                # ── term status ────────────────────────────────────────────────
                reporting_period_id = section.get('reportingAcademicPeriod', {}).get('id')
                if reporting_period_id and Term.objects.filter(external_sis_id=reporting_period_id).exists():
                    term_status = 'exists'
                else:
                    term_status = 'will_be_created'

                # ── course status ──────────────────────────────────────────────
                if subject_abbr and catalog_num:
                    cohort = Cohort.objects.filter(designator=subject_abbr).first()
                    if cohort and Course.objects.filter(cohort=cohort, catalog_number=catalog_num).exists():
                        course_status = 'exists'
                    else:
                        course_status = 'will_be_created'
                else:
                    course_status = 'missing_data'

                # ── highschool status ──────────────────────────────────────────
                if not building_code:
                    highschool_status = 'no_building_code'
                elif HighSchool.objects.filter(Q(sau=building_code) | Q(code=building_code)).exists():
                    highschool_status = 'exists'
                else:
                    highschool_status = 'not_found'

                # ── teacher status ─────────────────────────────────────────────
                banner_ids = [
                    next((c['value'] for c in e.get('instructor', {}).get('credentials', [])
                          if c.get('type') == 'bannerId'), None)
                    for e in roster
                ]
                banner_ids = [b for b in banner_ids if b]
                matches = Teacher.objects.filter(user__psid__in=banner_ids).count() if banner_ids else 0
                if matches > 1:
                    teacher_status = 'multiple_found'
                elif matches == 1:
                    teacher_status = 'exists'
                else:
                    primary_entry = next(
                        (r for r in roster if r.get('instructorRole') == 'primary'),
                        roster[0] if roster else None,
                    )
                    primary_creds = primary_entry.get('instructor', {}).get('credentials', []) if primary_entry else []
                    has_banner_id = any(c.get('type') == 'bannerId' for c in primary_creds)
                    has_username = any(c.get('type') == 'bannerUserName' for c in primary_creds)
                    if has_banner_id and has_username:
                        teacher_status = 'will_be_created'
                    else:
                        teacher_status = 'not_found'

                writer.writerow({
                    'id': section.get('id', ''),
                    'course_name': course_name,
                    'highschool': building_code,
                    'section_number': section.get('number', ''),
                    'class_number': section.get('code', ''),
                    'term_name': schedule_period.get('title', ''),
                    'term_code': schedule_period.get('code', ''),
                    'instructor_name': instructor_name,
                    'instructor_email': instructor_email,
                    'term_status': term_status,
                    'course_status': course_status,
                    'highschool_status': highschool_status,
                    'teacher_status': teacher_status,
                })

        self.stdout.write(self.style.SUCCESS(f'CSV written to {path} ({len(raw_sections)} rows)'))

    def _import(self, raw_sections, skip_certificates, term):
        from cis.services.sis_importer import SISImporter

        counts = SISImporter().import_sections(raw_sections, term, skip_certificates)

        for err in counts.get('errors', []):
            self.stdout.write(self.style.ERROR(f'  Error processing section {err["code"]}: {err["error"]}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nImport complete:\n'
            f'  Courses created:            {counts["course_created"]}\n'
            f'  Teachers created:           {counts["teacher_created"]}\n'
            f'  TeacherHighSchool created:  {counts["teacher_hs_created"]}\n'
            f'  Certificates created:       {counts["cert_created"]}\n'
            f'  Sections created:           {counts["section_created"]}\n'
            f'  Sections updated:           {counts["section_updated"]}\n'
            f'  Sections skipped:           {counts["section_skipped"]}\n'
        ))

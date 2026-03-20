import csv
import logging

from django.db.models import Q
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

        self.stdout.write('Fetching sections from Ethos...')
        raw_sections = ethos.get_sections(return_type='raw', period_id=period_id)
        self.stdout.write(f'Found {len(raw_sections)} sections.')

        if csv_path:
            self._write_csv(raw_sections, csv_path)

        if not do_create:
            self._dry_run(raw_sections)
            self.stdout.write(self.style.NOTICE('Dry run — pass --create to import into the database.'))
            return

        self._import(raw_sections, skip_certificates)

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

    def _import(self, raw_sections, skip_certificates):
        from cis.models.term import Term, AcademicYear
        from cis.models.course import Cohort, Course
        from cis.models.highschool import HighSchool
        from cis.models.teacher import Teacher, TeacherHighSchool, TeacherCourseCertificate
        from cis.models.section import ClassSection

        counts = {
            'term_created': 0,
            'course_created': 0,
            'teacher_created': 0,
            'teacher_hs_created': 0,
            'cert_created': 0,
            'section_created': 0,
            'section_updated': 0,
            'section_skipped': 0,
        }

        for section in raw_sections:
            try:
                self._process_section(
                    section, counts, skip_certificates,
                    Term, AcademicYear, Cohort, Course,
                    HighSchool, Teacher, TeacherHighSchool,
                    TeacherCourseCertificate, ClassSection,
                )
            except Exception as e:
                code = section.get('code', '?')
                self.stdout.write(self.style.ERROR(f'  Error processing section {code}: {e}'))
                logger.exception(f'Error processing section {code}')

        self.stdout.write(self.style.SUCCESS(
            f'\nImport complete:\n'
            f'  Terms created:              {counts["term_created"]}\n'
            f'  Courses created:            {counts["course_created"]}\n'
            f'  Teachers created:           {counts["teacher_created"]}\n'
            f'  TeacherHighSchool created:  {counts["teacher_hs_created"]}\n'
            f'  Certificates created:       {counts["cert_created"]}\n'
            f'  Sections created:           {counts["section_created"]}\n'
            f'  Sections updated:           {counts["section_updated"]}\n'
            f'  Sections skipped:           {counts["section_skipped"]}\n'
        ))

    def _process_section(
        self, section, counts, skip_certificates,
        Term, AcademicYear, Cohort, Course,
        HighSchool, Teacher, TeacherHighSchool,
        TeacherCourseCertificate, ClassSection,
    ):
        # ── a. TERM + ACADEMIC YEAR ────────────────────────────────────────────
        reporting_period_id = section.get('reportingAcademicPeriod', {}).get('id')
        term = Term.objects.filter(external_sis_id=reporting_period_id).first() if reporting_period_id else None

        if term is None:
            schedule_period = section.get('scheduleAcademicPeriod', {})
            title = schedule_period.get('title', '')
            code = schedule_period.get('code', '')
            year_str = title.split()[-1] if title else ''

            if not year_str:
                self.stdout.write(self.style.WARNING(
                    f'  Skipping section {section.get("code")} — cannot determine term year'
                ))
                counts['section_skipped'] += 1
                return

            academic_year = AcademicYear.get_or_add(name=year_str)
            term = Term.get_or_add(
                academic_year, label=title, code=code,
                external_sis_id=reporting_period_id,
            )
            counts['term_created'] += 1
            self.stdout.write(f'  Created term: {title} ({code})')

        # ── b. COHORT + COURSE ─────────────────────────────────────────────────
        course_data = section.get('course', {})
        subject = course_data.get('subject', {})
        subject_abbr = subject.get('abbreviation', '')
        subject_title = subject.get('title', subject_abbr)
        catalog_num = course_data.get('number', '')
        titles = course_data.get('titles', [{}])
        course_title = titles[0].get('value', '') if titles else ''

        if not subject_abbr or not catalog_num:
            self.stdout.write(self.style.WARNING(
                f'  Skipping section {section.get("code")} — missing subject or catalog number'
            ))
            counts['section_skipped'] += 1
            return

        cohort = Cohort.get_or_add(cohort_designator=subject_abbr, title=subject_title)
        course, course_created = Course.objects.get_or_create(
            cohort=cohort,
            catalog_number=catalog_num,
            campus=None,
            defaults={
                'title': course_title,
                'name': f'{subject_abbr} {catalog_num}',
                'status': 'Active',
            },
        )
        if course_created:
            counts['course_created'] += 1

        # ── c. HIGH SCHOOL ─────────────────────────────────────────────────────
        highschool = None
        try:
            building_code = section['instructionalEvents'][0]['locations'][0]['location']['building']['code']
        except (KeyError, IndexError):
            building_code = None

        if building_code:
            highschool = HighSchool.objects.filter(Q(sau=building_code) | Q(code=building_code)).first()
            if highschool is None:
                self.stdout.write(self.style.WARNING(
                    f'  No HighSchool found for building code "{building_code}" '
                    f'(section {section.get("code")})'
                ))

        # ── d. INSTRUCTORS ─────────────────────────────────────────────────────
        teacher = None
        roster = section.get('instructorRosterDetails', [])

        teachers_found = []
        for roster_entry in roster:
            credentials = roster_entry.get('instructor', {}).get('credentials', [])
            banner_id = next((c['value'] for c in credentials if c.get('type') == 'bannerId'), None)
            if not banner_id:
                continue
            t = Teacher.objects.filter(user__psid=banner_id).first()
            if t:
                teachers_found.append((t, roster_entry))

        if len(teachers_found) > 1:
            self.stdout.write(self.style.WARNING(
                f'  Multiple DB teachers found for section {section.get("code")} — skipping teacher link'
            ))
        elif len(teachers_found) == 1:
            teacher = teachers_found[0][0]
        else:
            # No DB match — create from primary instructor entry (fall back to first)
            entry = next(
                (r for r in roster if r.get('instructorRole') == 'primary'),
                roster[0] if roster else None,
            )
            if entry:
                instructor = entry.get('instructor', {})
                credentials = instructor.get('credentials', [])
                banner_id = next((c['value'] for c in credentials if c.get('type') == 'bannerId'), None)
                banner_username = next((c['value'] for c in credentials if c.get('type') == 'bannerUserName'), None)
                names = instructor.get('names', [{}])
                first_name = names[0].get('firstName', '') if names else ''
                last_name = names[0].get('lastName', '') if names else ''
                email = (banner_username + '@ewu.edu') if banner_username else None

                if banner_id and email:
                    teacher = Teacher.get_or_add(
                        psid=banner_id,
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                    )
                    counts['teacher_created'] += 1
                    self.stdout.write(f'  Created teacher: {first_name} {last_name} ({email})')

        # ── e. TEACHER ↔ HIGHSCHOOL ────────────────────────────────────────────
        teacher_hs = None
        if teacher and highschool:
            teacher_hs, created = TeacherHighSchool.objects.get_or_create(
                teacher=teacher,
                highschool=highschool,
                defaults={'status': 'In the Program'},
            )
            if created:
                counts['teacher_hs_created'] += 1

        # ── f. TEACHER COURSE CERTIFICATE ─────────────────────────────────────
        if teacher_hs and course and not skip_certificates:
            _, created = TeacherCourseCertificate.objects.get_or_create(
                course=course,
                teacher_highschool=teacher_hs,
                defaults={'status': 'Teaching'},
            )
            if created:
                counts['cert_created'] += 1

        # ── g. CLASS SECTION ───────────────────────────────────────────────────
        try:
            class_number = int(section['code'])
        except (KeyError, ValueError):
            self.stdout.write(self.style.WARNING(f'  Skipping section — invalid code: {section.get("code")}'))
            counts['section_skipped'] += 1
            return

        section_number = section.get('number', '')
        start_date = section.get('startOn') or None
        end_date = section.get('endOn') or None
        status_category = section.get('status', {}).get('category', '')
        status = 'A' if status_category == 'open' else 'C'
        max_enrollment = section.get('maxEnrollment', 0) or 0

        obj, created = ClassSection.objects.update_or_create(
            class_number=class_number,
            term=term,
            defaults={
                'section_number': section_number,
                'course': course,
                'highschool': highschool,
                'teacher': teacher,
                'start_date': start_date,
                'end_date': end_date,
                'status': status,
                'meta': section,
                'max_enrollment': max_enrollment,
            },
        )
        if created:
            counts['section_created'] += 1
        else:
            counts['section_updated'] += 1

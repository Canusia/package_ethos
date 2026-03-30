import logging

from django.db.models import Q

logger = logging.getLogger(__name__)


class SectionImporter:
    """Upsert CIS records for a list of raw Ethos section dicts."""

    def import_sections(self, raw_sections, term, skip_certificates=False) -> dict:
        """
        Process raw Ethos section dicts and upsert CIS records for the given term.
        Returns counts dict with keys: course_created, teacher_created,
        teacher_hs_created, cert_created, section_created, section_updated,
        section_skipped, errors.
        """
        from cis.models.course import Cohort, Course
        from cis.models.highschool import HighSchool
        from cis.models.teacher import Teacher, TeacherHighSchool, TeacherCourseCertificate
        from cis.models.section import ClassSection

        counts = {k: 0 for k in [
            'course_created', 'teacher_created',
            'teacher_hs_created', 'cert_created',
            'section_created', 'section_updated', 'section_skipped',
        ]}
        errors = []

        for section in raw_sections:
            try:
                self._process_section(
                    section, term, counts, skip_certificates,
                    Cohort, Course,
                    HighSchool, Teacher, TeacherHighSchool,
                    TeacherCourseCertificate, ClassSection,
                )
            except Exception as e:
                code = section.get('code', '?')
                logger.exception(f'Error processing section {code}')
                errors.append({'code': code, 'error': str(e)})

        counts['errors'] = errors
        return counts

    def _process_section(
        self, section, term, counts, skip_certificates,
        Cohort, Course,
        HighSchool, Teacher, TeacherHighSchool,
        TeacherCourseCertificate, ClassSection,
    ):
        # ── a. COHORT + COURSE ─────────────────────────────────────────────────
        course_data = section.get('course', {})
        subject = course_data.get('subject', {})
        subject_abbr = subject.get('abbreviation', '')
        subject_title = subject.get('title', subject_abbr)
        catalog_num = course_data.get('number', '')
        titles = course_data.get('titles', [{}])
        course_title = titles[0].get('value', '') if titles else ''

        if not subject_abbr or not catalog_num:
            logger.warning(
                f'Skipping section {section.get("code")} — missing subject or catalog number'
            )
            counts['section_skipped'] += 1
            return

        cohort = Cohort.get_or_add(cohort_designator=subject_abbr, title=subject_title)
        course_guid = course_data.get('id', '') or None
        course, course_created = Course.objects.get_or_create(
            cohort=cohort,
            catalog_number=catalog_num,
            campus=None,
            defaults={
                'title': course_title,
                'name': f'{subject_abbr} {catalog_num}',
                'status': 'Active',
                'external_sis_id': course_guid,
            },
        )
        if course_created:
            counts['course_created'] += 1

        # ── b. HIGH SCHOOL ─────────────────────────────────────────────────────
        highschool = None
        try:
            building_code = section['instructionalEvents'][0]['locations'][0]['location']['building']['code']
        except (KeyError, IndexError):
            building_code = None

        if building_code:
            highschool = HighSchool.objects.filter(Q(sau=building_code) | Q(code=building_code)).first()
            if highschool is None:
                logger.warning(
                    f'No HighSchool found for building code "{building_code}" '
                    f'(section {section.get("code")})'
                )

        # ── c. INSTRUCTORS ─────────────────────────────────────────────────────
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
            logger.warning(
                f'Multiple DB teachers found for section {section.get("code")} — skipping teacher link'
            )
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

        # ── d. TEACHER ↔ HIGHSCHOOL ────────────────────────────────────────────
        teacher_hs = None
        if teacher and highschool:
            teacher_hs, created = TeacherHighSchool.objects.get_or_create(
                teacher=teacher,
                highschool=highschool,
                defaults={'status': 'In the Program'},
            )
            if created:
                counts['teacher_hs_created'] += 1

        # ── e. TEACHER COURSE CERTIFICATE ─────────────────────────────────────
        if teacher_hs and course and not skip_certificates:
            _, created = TeacherCourseCertificate.objects.get_or_create(
                course=course,
                teacher_highschool=teacher_hs,
                defaults={'status': 'Teaching'},
            )
            if created:
                counts['cert_created'] += 1

        # ── f. CLASS SECTION ───────────────────────────────────────────────────
        try:
            # class_number = int(section['code'])
            class_number = section['code']
        except (KeyError, ValueError):
            logger.warning(f'Skipping section — invalid code: {section.get("code")}')
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

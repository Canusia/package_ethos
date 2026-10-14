"""MyCE vs Banner grades and registration status, one class at a time.

Backs the "Banner vs MyCE Grades" report. For each class with a Banner section
GUID it reads the section's registrations and unverified grades from Banner in
two (paged) calls; a class without one falls back to per-registration calls.
Rows are matched on the section-registration GUID (``StudentRegistration.sis_id``).

Read-only: every Banner call is a GET. A failing class gets "Banner error"
rows and the rest of the report carries on.

Tenant hooks (``get_tenant_override('grade_sis_pusher', ...)``, both optional):
    last_sent(registration_ids) -> {str(id): datetime}   when MyCE last sent the grade
    banner_registered_statuses() -> iterable of MyCE statuses expected to be
                                    "registered" in Banner (default REGISTERED_STATUSES)
"""
import json
import logging
from collections import OrderedDict
from urllib.parse import urlencode

from .grade_push_config import guid_of
from .grade_push_lookup import BannerLookupError, _get, _person_name

logger = logging.getLogger(__name__)

# MyCE statuses whose Banner registration should be "registered"; any other
# status should be not registered (or absent) in Banner.
REGISTERED_STATUSES = ('registered', 'enrolled')

PAGE_SIZE = 100

# Result values
MATCH = 'Match'
GRADE_DIFFERS = 'Grade differs'
GRADE_MISSING_IN_BANNER = 'Grade missing in Banner'
GRADE_ONLY_IN_BANNER = 'Grade only in Banner'
STATUS_DIFFERS = 'Status differs'
MISSING_IN_BANNER = 'Missing in Banner'
ONLY_IN_BANNER = 'Only in Banner'
NO_REGISTRATION_ID = 'No Banner registration ID'
BANNER_ERROR = 'Banner error'

COLUMNS = (
    'Result', 'Term Code', 'Term', 'Course', 'Course Title', 'CRN', 'Section',
    'Instructor', 'High School', 'Student', 'PSID', 'Email',
    'MyCE Status', 'Banner Status', 'Banner Status Reason', 'Status Match',
    'MyCE Grade', 'Section Grade Status', 'Banner Grade', 'Banner Grade Type',
    'Grade Match', 'Last Sent', 'Banner Grade Record ID',
    'Banner Section Registration ID', 'Error',
)


def _hook(name):
    from cis.services.tenant_services import get_tenant_override
    return get_tenant_override('grade_sis_pusher', name)


def registered_statuses():
    fn = _hook('banner_registered_statuses')
    if fn is None:
        return set(REGISTERED_STATUSES)
    return set(fn())


def last_sent_map(registration_ids):
    """{str(registration id): datetime} from the tenant hook ({} without one)."""
    fn = _hook('last_sent')
    if fn is None or not registration_ids:
        return {}
    try:
        return {str(k): v for k, v in (fn(registration_ids) or {}).items()}
    except Exception:
        logger.exception('grade_comparison: last_sent hook failed')
        return {}


# --- Banner reads ---------------------------------------------------------------

def _get_all(client, path, message_type):
    """Every row of a paged Banner list (offset/limit)."""
    rows, offset = [], 0
    sep = '&' if '?' in path else '?'
    while True:
        page = _get(client, f'{path}{sep}offset={offset}&limit={PAGE_SIZE}', message_type, list)
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def _registration_row(raw):
    status = raw.get('status') or {}
    return {
        'id': raw.get('id') or '',
        'registrant': (raw.get('registrant') or {}).get('id') or '',
        'status': status.get('registrationStatus') or '',
        'reason': status.get('sectionRegistrationStatusReason') or '',
    }


def _final_grade(raw, final_type_id):
    """(letter, type code, record id) of the FINAL grade on an unverified-grade record."""
    grades = ((raw.get('details') or {}).get('grades')) or []
    for g in grades:
        gtype = g.get('type') or {}
        if (final_type_id and gtype.get('id') == final_type_id) or gtype.get('code') == 'FINAL':
            return ((g.get('grade') or {}).get('value') or '', gtype.get('code') or '',
                    raw.get('id') or '')
    return '', '', raw.get('id') or ''


def banner_section(client, section_guid, final_type_id):
    """({reg id: registration}, {reg id: (grade, type, record id)}) for a Banner section."""
    criteria = urlencode({'criteria': json.dumps({'section': {'id': section_guid}})})
    regs = _get_all(client, f'section-registrations?{criteria}', 'grade_compare_registrations')
    # student-unverified-grades rejects a `section` criteria; the named query works.
    named = urlencode({'section': json.dumps({'section': {'id': section_guid}})})
    grades = _get_all(client, f'student-unverified-grades?{named}', 'grade_compare_grades')
    registrations = {r['id']: r for r in map(_registration_row, regs) if r['id']}
    by_reg = {}
    for raw in grades:
        reg_id = (raw.get('sectionRegistration') or {}).get('id')
        if reg_id:
            by_reg[reg_id] = _final_grade(raw, final_type_id)
    return registrations, by_reg


def banner_registration(client, registration_guid, final_type_id):
    """(registration or None, grade tuple or None) for one section registration."""
    try:
        raw = _get(client, f'section-registrations/{registration_guid}',
                   'grade_compare_registration', dict)
    except BannerLookupError as exc:
        if exc.status == 404:
            return None, None
        raise
    criteria = urlencode({'criteria': json.dumps({'sectionRegistration': {'id': registration_guid}})})
    grades = _get(client, f'student-unverified-grades?{criteria}', 'grade_compare_grades', list)
    return _registration_row(raw), (_final_grade(grades[0], final_type_id) if grades else None)


# --- comparison -------------------------------------------------------------------

def _clean_grade(value):
    value = (value or '').strip()
    return '' if value == '-' else value


def _section_cells(section):
    course = section.course
    teacher = getattr(section, 'teacher', None)
    teacher_user = getattr(teacher, 'user', None)
    term = section.term
    return {
        'Term Code': getattr(term, 'code', '') or '',
        'Term': getattr(term, 'label', '') or '',
        'Course': getattr(course, 'name', '') or '',
        'Course Title': getattr(course, 'title', '') or '',
        'CRN': section.class_number or '',
        'Section': section.section_number or '',
        'Instructor': (f'{teacher_user.first_name} {teacher_user.last_name}'.strip()
                       if teacher_user else ''),
        'Section Grade Status': {'submitted': 'Submitted', 'saved': 'Draft'}.get(
            section.grade_status or '', 'Not started'),
    }


def compare_registration(registration, banner_reg, banner_grade, registered, last_sent):
    """One CSV row (dict keyed by COLUMNS) for a MyCE registration."""
    user = registration.student.user
    row = dict.fromkeys(COLUMNS, '')
    row.update(_section_cells(registration.class_section))
    row.update({
        'High School': getattr(registration.highschool, 'name', '') or '',
        'Student': f'{user.last_name}, {user.first_name}',
        'PSID': user.psid or '',
        'Email': user.email or '',
        'MyCE Status': registration.get_status_display(),
        'MyCE Grade': _clean_grade(registration.grade),
        'Banner Section Registration ID': str(registration.sis_id or ''),
        'Last Sent': last_sent.strftime('%m/%d/%Y %I:%M %p') if last_sent else '',
    })
    if not registration.sis_id:
        row['Result'] = NO_REGISTRATION_ID
        return row
    if banner_reg is None:
        row['Result'] = MISSING_IN_BANNER
        row['Status Match'] = 'Y' if registration.status not in registered else 'N'
        return row

    row['Banner Status'] = banner_reg['status']
    row['Banner Status Reason'] = banner_reg['reason']
    status_ok = (banner_reg['status'] == 'registered') == (registration.status in registered)
    row['Status Match'] = 'Y' if status_ok else 'N'

    banner_letter, banner_type, record_id = banner_grade or ('', '', '')
    row['Banner Grade'] = banner_letter
    row['Banner Grade Type'] = banner_type
    row['Banner Grade Record ID'] = record_id
    myce = row['MyCE Grade']
    if myce == banner_letter:
        grade_problem = None
    elif not banner_letter:
        grade_problem = GRADE_MISSING_IN_BANNER
    elif not myce:
        grade_problem = GRADE_ONLY_IN_BANNER
    else:
        grade_problem = GRADE_DIFFERS
    row['Grade Match'] = 'N' if grade_problem else 'Y'

    problems = [p for p in (grade_problem, None if status_ok else STATUS_DIFFERS) if p]
    row['Result'] = '; '.join(problems) or MATCH
    return row


def _banner_only_row(section, banner_reg, banner_grade, client, names):
    row = dict.fromkeys(COLUMNS, '')
    row.update(_section_cells(section))
    person = banner_reg['registrant']
    if person and person not in names:
        names[person] = _person_name(client, person)
    letter, gtype, record_id = banner_grade or ('', '', '')
    row.update({
        'Result': ONLY_IN_BANNER,
        'Student': names.get(person, ''),
        'Banner Status': banner_reg['status'],
        'Banner Status Reason': banner_reg['reason'],
        'Banner Grade': letter,
        'Banner Grade Type': gtype,
        'Banner Grade Record ID': record_id,
        'Banner Section Registration ID': banner_reg['id'],
    })
    return row


def _error_row(registration, message, registered, last_sent):
    row = compare_registration(registration, None, None, registered, last_sent)
    row.update({'Result': BANNER_ERROR, 'Status Match': '', 'Error': message})
    return row


def compare_section(client, section, registrations, all_sis_ids, *, final_type_id,
                    include_banner_only, registered, last_sent, names):
    """Rows for one class: its selected MyCE registrations, plus Banner-only rows.

    `all_sis_ids` holds every MyCE registration GUID of the class (not only the
    selected statuses), so a filtered-out MyCE row never shows as "Only in Banner".
    """
    section_guid = section.sis_id
    try:
        if section_guid:
            banner_regs, banner_grades = banner_section(client, str(section_guid), final_type_id)
        else:
            banner_regs, banner_grades = {}, {}
            for reg in registrations:
                if reg.sis_id:
                    banner_reg, grade = banner_registration(client, str(reg.sis_id), final_type_id)
                    if banner_reg:
                        banner_regs[banner_reg['id']] = banner_reg
                    if grade:
                        banner_grades[str(reg.sis_id)] = grade
    except BannerLookupError as exc:
        return [_error_row(r, str(exc), registered, last_sent.get(str(r.id)))
                for r in registrations]

    rows = []
    for reg in registrations:
        key = str(reg.sis_id or '')
        rows.append(compare_registration(
            reg, banner_regs.get(key), banner_grades.get(key), registered,
            last_sent.get(str(reg.id))))
    if include_banner_only and section_guid:
        for reg_id, banner_reg in banner_regs.items():
            if reg_id not in all_sis_ids:
                rows.append(_banner_only_row(
                    section, banner_reg, banner_grades.get(reg_id), client, names))
    return rows


def compare(registrations, all_registrations, *, include_banner_only=True,
            only_differences=False, client_for=None):
    """Yield CSV rows for `registrations` (a StudentRegistration queryset).

    `all_registrations` is the unfiltered queryset of the same classes, used
    only for "Only in Banner" detection. `client_for(campus)` returns the Ethos
    client for a class's course campus (default: grade_push's per-campus cache).
    """
    from .grade_push import _get_client
    client_for = client_for or _get_client

    registrations = list(registrations.select_related(
        'student__user', 'highschool', 'class_section__term', 'class_section__course',
        'class_section__course__campus', 'class_section__teacher__user'))
    by_section = OrderedDict()
    for reg in registrations:
        by_section.setdefault(reg.class_section_id, []).append(reg)

    sis_ids = {}
    for section_id, sis_id in all_registrations.filter(
            class_section_id__in=by_section.keys()).values_list('class_section_id', 'sis_id'):
        if sis_id:
            sis_ids.setdefault(section_id, set()).add(str(sis_id))

    registered = registered_statuses()
    last_sent = last_sent_map([r.id for r in registrations])
    names = {}
    for section_id, regs in by_section.items():
        section = regs[0].class_section
        campus = getattr(section.course, 'campus', None)
        rows = _section_rows(client_for, campus, section, regs, sis_ids.get(section_id, set()),
                             include_banner_only, registered, last_sent, names)
        for row in rows:
            if only_differences and row['Result'] == MATCH:
                continue
            yield row


def _section_rows(client_for, campus, section, regs, all_sis_ids, include_banner_only,
                  registered, last_sent, names):
    """compare_section run under the class's campus (its Ethos credentials and SIS GUIDS)."""
    from cis.campus_context import campus_context, is_multi_campus

    def run():
        client = client_for(campus)
        try:
            final_type_id = guid_of(client._load_sis_guids().get('final_grade_type'))
        except Exception:
            final_type_id = ''
        return compare_section(
            client, section, regs, all_sis_ids, final_type_id=final_type_id,
            include_banner_only=include_banner_only, registered=registered,
            last_sent=last_sent, names=names)

    try:
        if campus is None or not is_multi_campus():
            return run()
        with campus_context(campus):
            return run()
    except Exception as exc:  # credentials, network, bad data: one class, not the report
        logger.exception('grade_comparison: class %s failed', section.pk)
        return [_error_row(r, str(exc) or type(exc).__name__, registered,
                           last_sent.get(str(r.id))) for r in regs]

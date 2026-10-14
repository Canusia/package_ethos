"""Push one final grade to Banner as a student-unverified-grade.

Entry point for the grades package's SIS push, reached through the tenant
service ``myce_tenant_configs/services/grade_sis_pusher.py``. This module never
imports ``grades``: it returns a plain object carrying the attributes of
``grades.services.sis_push.GradePushResult`` (success, record_id, error, log_url).

Configuration comes from the ``sis_guids`` setting:
    final_grade_type    {"id": guid}          required
    grade_map           {"A": guid, ...}      required, exact match after strip()
    grade_submitted_by  {"id": guid}          required; Banner rejects a push without it

Scale letters with no grade_map entry do not block a push of a mapped letter;
config_errors() reports them for the settings page.
"""
from types import SimpleNamespace

from django.urls import NoReverseMatch, reverse

from .grade_push_config import guid_of
from .library.ethos import Ethos
from .library.grades import UnverifiedGradesLookupError

AUTH_STATUS_CODES = (401, 403)

# One Ethos client (and its auth-token cache) per campus, reused across calls
# in this process/batch, so a run of many registrations authenticates once per
# campus instead of once per row. Keyed by campus pk; None is the
# deployment-wide client. Tests reset it with `grade_push._clients.clear()`.
_clients = {}


def _get_client(campus=None):
    """The Ethos client for `campus`, or for the ambient campus when None.

    Single-campus deployments always share the one deployment-wide client
    (Ethos ignores the campus there). Multi-campus resolves the ambient campus
    before keying, so a cached client is never reused for another college.
    """
    from cis.campus_context import current_campus_or_none, is_multi_campus

    if not is_multi_campus():
        campus = None
    elif campus is None:
        campus = current_campus_or_none()
    key = getattr(campus, 'pk', None)
    if key not in _clients:
        _clients[key] = Ethos(campus=campus)
    return _clients[key]


def _grade_scale():
    """Letters on the tenant's MyCE grade scale ([] when the tenant has no hook).

    Resolved through the tenant seam so ethos never imports grades.
    """
    from cis.services.tenant_services import get_tenant_override
    fn = get_tenant_override('grade_sis_pusher', 'grade_scale')
    if fn is None:
        return []
    try:
        return [str(g).strip() for g in (fn() or []) if str(g).strip()]
    except Exception:
        return []


def required_errors(guids):
    """Problems that stop every push: Banner rejects the request without these."""
    errors = []
    if not guid_of(guids.get('final_grade_type')):
        errors.append('sis_guids.final_grade_type.id is not set.')
    grade_map = guids.get('grade_map')
    if not isinstance(grade_map, dict) or not grade_map:
        errors.append('sis_guids.grade_map is empty.')
    if not guid_of(guids.get('grade_submitted_by')):
        errors.append('sis_guids.grade_submitted_by.id is not set (Banner requires submittedBy).')
    return errors


def unmapped_grades(guids):
    """Scale letters with no grade_map entry, in scale order."""
    grade_map = guids.get('grade_map')
    grade_map = grade_map if isinstance(grade_map, dict) else {}
    return [g for g in _grade_scale() if g not in grade_map]


def config_errors(guids=None):
    """Human-readable problems with the grade-push configuration ([] = OK)."""
    if guids is None:
        guids = _get_client()._load_sis_guids()
    return required_errors(guids) + [
        f"Grade '{g}' has no Banner mapping." for g in unmapped_grades(guids)]


def _log_url(log):
    if log is None:
        return ''
    try:
        return reverse('ethos:ethos_log_detail', args=[log.pk])
    except NoReverseMatch:
        return ''


def _result(success, record_id=None, error='', log=None):
    return SimpleNamespace(
        success=success, record_id=record_id, error=error, log_url=_log_url(log))


def _submission_error(log):
    """Error message for a failed submission, naming authentication on 401/403."""
    if log.response_status in AUTH_STATUS_CODES:
        return (
            f'Ethos authentication/authorisation failed (HTTP {log.response_status}). '
            'Check the Ethos credentials/authorization configuration.'
        )
    return log.error_message or f'HTTP {log.response_status}'


def _record_campus(registration):
    """The campus that owns `registration`: its course's campus, or None."""
    section = getattr(registration, 'class_section', None)
    course = getattr(section, 'course', None)
    return getattr(course, 'campus', None)


def push_final_grade(registration, grade, existing_record_id=None):
    """Create or update the Banner unverified FINAL grade for `registration`.

    The record decides the campus, as in the host's mirror_to_sis: the push
    runs inside the registration's course campus, so the Ethos credentials
    and the campus-scoped sis_guids are that campus's, whatever the caller's
    ambient campus. A campus-less course keeps the ambient campus
    (single-campus: unchanged).
    """
    campus = _record_campus(registration)
    if campus is None:
        return _push_final_grade(registration, grade, existing_record_id, None)
    from cis.campus_context import campus_context
    with campus_context(campus):
        return _push_final_grade(registration, grade, existing_record_id, campus)


def _push_final_grade(registration, grade, existing_record_id, campus):
    """push_final_grade's body, run under the registration's campus."""
    ethos = _get_client(campus)
    guids = ethos._load_sis_guids()

    errors = required_errors(guids)
    if errors:
        return _result(False, error=' '.join(errors))

    if not registration.sis_id:
        return _result(False, error=(
            'No section-registration id. Use "Look up Section Registration ID" '
            'on the registration first.'))

    key = (grade or '').strip()
    grade_id = guids['grade_map'].get(key)
    if not grade_id:
        return _result(False, error=(
            f"Grade '{key}' has no Banner mapping in sis_guids.grade_map."))

    submitted_by = guid_of(guids.get('grade_submitted_by')) or None
    section_registration_id = str(registration.sis_id)

    record_id = existing_record_id
    if not record_id:
        try:
            existing = ethos.get_unverified_grades(section_registration_id)
        except UnverifiedGradesLookupError as exc:
            # A failed lookup is not "no existing record": treating it as
            # such would POST a duplicate instead of updating the record
            # that may well already exist in Banner.
            return _result(False, error=(
                'Could not check for an existing Banner record '
                f'(HTTP {exc.status_code}).'))
        if existing:
            record_id = existing[0].get('id')

    success, log = ethos.submit_unverified_grade(
        section_registration_id, grade_id, guid_of(guids.get('final_grade_type')),
        submitted_by_id=submitted_by, record_id=record_id)

    if not success:
        return _result(
            False, record_id=record_id, log=log, error=_submission_error(log))

    return _result(True, record_id=log.response_json.get('id') or record_id, log=log)

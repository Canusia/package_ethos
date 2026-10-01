"""Push one final grade to Banner as a student-unverified-grade.

Entry point for the grades package's SIS push, reached through the tenant
service ``myce_tenant_configs/services/grade_sis_pusher.py``. This module never
imports ``grades``: it returns a plain object carrying the attributes of
``grades.services.sis_push.GradePushResult`` (success, record_id, error, log_url).

Configuration comes from the ``sis_guids`` setting:
    final_grade_type    {"id": guid}          required
    grade_map           {"A": guid, ...}      required, exact match after strip()
    grade_submitted_by  {"id": guid}          optional; omitted when blank
"""
from types import SimpleNamespace

from django.urls import NoReverseMatch, reverse

from .library.ethos import Ethos

AUTH_STATUS_CODES = (401, 403)


def config_errors(guids=None):
    """Human-readable problems with the grade-push configuration ([] = OK)."""
    if guids is None:
        guids = Ethos()._load_sis_guids()
    errors = []
    if not (guids.get('final_grade_type') or {}).get('id'):
        errors.append('sis_guids.final_grade_type.id is not set.')
    grade_map = guids.get('grade_map')
    if not isinstance(grade_map, dict) or not grade_map:
        errors.append('sis_guids.grade_map is empty.')
    return errors


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


def push_final_grade(registration, grade, existing_record_id=None):
    """Create or update the Banner unverified FINAL grade for `registration`."""
    ethos = Ethos()
    guids = ethos._load_sis_guids()

    errors = config_errors(guids)
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

    submitted_by = (guids.get('grade_submitted_by') or {}).get('id') or None
    section_registration_id = str(registration.sis_id)

    record_id = existing_record_id
    if not record_id:
        existing = ethos.get_unverified_grades(section_registration_id)
        if existing:
            record_id = existing[0].get('id')

    success, log = ethos.submit_unverified_grade(
        section_registration_id, grade_id, guids['final_grade_type']['id'],
        submitted_by_id=submitted_by, record_id=record_id)

    if not success:
        return _result(
            False, record_id=record_id, log=log, error=_submission_error(log))

    return _result(True, record_id=log.response_json.get('id') or record_id, log=log)

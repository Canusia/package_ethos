"""
GradesMixin — grade reads and final grade submission.

CE programs sync final grades back to the SIS at term end.
Reference lookups (valid grade values, modes, schemes) are also here
so callers can validate before submitting.
"""

import json
import logging

from urllib.parse import urlencode

from .base import EthosBase

logger = logging.getLogger(__name__)

UNVERIFIED_GRADES_ACCEPT = 'application/vnd.hedtech.integration.v1+json'
UNVERIFIED_GRADES_SUBMISSION = (
    'application/vnd.hedtech.integration.student-unverified-grades-submissions.v1+json'
)
NIL_GUID = '00000000-0000-0000-0000-000000000000'


class UnverifiedGradesLookupError(Exception):
    """A non-OK response to the Banner unverified-grades lookup.

    Distinguishes "the lookup itself failed" from "Banner has no record" ([]):
    the latter means POST (create), the former must not POST at all.
    """

    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f'get_unverified_grades failed: HTTP {status_code}')


class GradesMixin(EthosBase):
    """Grade reads and write operations for the CE workflow."""

    def get_student_grades(self, person_id, period_id=None, **kwargs):
        """Return grade records for a student, optionally filtered by academic period."""
        criteria = {'student': {'id': person_id}}
        if period_id:
            criteria['academicPeriod'] = {'id': period_id}
        url = f'{self.URL}/api/student-grades?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('student-grades') or 'application/json'
        resp, log = self._api_request('GET', url, 'student_grades', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_student_grades failed: %s %s', resp.status_code, resp.text)
        return []

    def get_grade_definitions(self, grade_scheme_id=None, **kwargs):
        """Return valid grade values (A, B, C, …), optionally scoped to a grade scheme."""
        criteria = {}
        if grade_scheme_id:
            criteria['scheme'] = {'id': grade_scheme_id}
        base = f'{self.URL}/api/grade-definitions'
        url = (base + '?' + urlencode({'criteria': json.dumps(criteria)})) if criteria else base
        accept = self.get_preferred_accept_header('grade-definitions') or 'application/json'
        resp, log = self._api_request('GET', url, 'grade_definitions', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_grade_definitions failed: %s %s', resp.status_code, resp.text)
        return []

    def get_grade_modes(self, **kwargs):
        """Return the reference list of grading modes (standard, audit, pass/fail, etc.)."""
        url = f'{self.URL}/api/grade-modes'
        accept = self.get_preferred_accept_header('grade-modes') or 'application/json'
        resp, log = self._api_request('GET', url, 'grade_modes', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_grade_modes failed: %s %s', resp.status_code, resp.text)
        return []

    def get_student_gpa(self, person_id, **kwargs):
        """Return cumulative and period GPA records for a student."""
        criteria = {'student': {'id': person_id}}
        url = f'{self.URL}/api/student-grade-point-averages?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('student-grade-point-averages') or 'application/json'
        resp, log = self._api_request('GET', url, 'student_gpa', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_student_gpa failed: %s %s', resp.status_code, resp.text)
        return []

    def get_section_grade_types(self, section_id, **kwargs):
        """Return the grade types that apply to a specific section."""
        criteria = {'section': {'id': section_id}}
        url = f'{self.URL}/api/section-grade-types?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('section-grade-types') or 'application/json'
        resp, log = self._api_request('GET', url, 'section_grade_types', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_section_grade_types failed: %s %s', resp.status_code, resp.text)
        return []

    def submit_student_grade(self, grade_id, grade_def_id, graded_on, **kwargs):
        """Submit a final grade for a student course registration.

        Args:
            grade_id: The Ethos GUID of the student-grades record to update.
            grade_def_id: The Ethos GUID of the grade definition (e.g. the "A" record).
            graded_on: ISO date string, e.g. "2026-05-15".

        Returns:
            Updated grade record dict, or None on failure.
        """
        url = f'{self.URL}/api/student-grades/{grade_id}'
        accept = self.get_preferred_accept_header('student-grades') or 'application/json'
        payload = json.dumps({
            'id': grade_id,
            'grade': {'detail': {'id': grade_def_id}},
            'submittedOn': graded_on,
        })
        resp, log = self._api_request(
            'PUT', url, 'submit_student_grade',
            data=payload,
            headers={
                'Accept': accept,
                'Content-Type': accept,
            },
            **kwargs,
        )
        if resp.ok:
            return resp.json()
        logger.error('submit_student_grade failed: %s %s', resp.status_code, resp.text)
        return None

    def get_unverified_grades(self, section_registration_id, **kwargs):
        """Return student-unverified-grades records for one section registration.

        An empty list means Banner has none, so a submission must POST (create).
        Raises `UnverifiedGradesLookupError` when the lookup request itself
        fails (non-OK response): that must not be mistaken for "no existing
        record" by a caller deciding POST vs PUT, since it would silently
        POST a duplicate instead of updating the record that may well exist.
        """
        criteria = {'sectionRegistration': {'id': section_registration_id}}
        url = f'{self.URL}/api/student-unverified-grades?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('student-unverified-grades') or UNVERIFIED_GRADES_ACCEPT
        resp, log = self._api_request(
            'GET', url, 'student_unverified_grades', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_unverified_grades failed: %s %s', resp.status_code, resp.text)
        raise UnverifiedGradesLookupError(resp.status_code)

    def submit_unverified_grade(self, section_registration_id, grade_id, grade_type_id,
                                submitted_by_id=None, record_id=None, **kwargs):
        """Create (POST) or update (PUT) a Banner unverified grade.

        `submissions` is part of the Content-Type, not the URL. `submittedBy` is
        optional in the schema and omitted when not given.

        Returns:
            (success: bool, log: EthosLog). On success the record id is
            ``log.response_json.get('id')``.
        """
        payload = {
            'id': record_id or NIL_GUID,
            'sectionRegistration': {'id': section_registration_id},
            'grade': {'type': {'id': grade_type_id}, 'grade': {'id': grade_id}},
        }
        if submitted_by_id:
            payload['submittedBy'] = {'id': submitted_by_id}

        if record_id:
            method, url = 'PUT', f'{self.URL}/api/student-unverified-grades/{record_id}'
        else:
            method, url = 'POST', f'{self.URL}/api/student-unverified-grades'

        accept = self.get_preferred_accept_header('student-unverified-grades') or UNVERIFIED_GRADES_ACCEPT
        resp, log = self._api_request(
            method, url, 'submit_unverified_grade',
            data=json.dumps(payload),
            headers={'Accept': accept, 'Content-Type': UNVERIFIED_GRADES_SUBMISSION},
            **kwargs,
        )
        if not resp.ok:
            logger.error('submit_unverified_grade failed: %s %s', resp.status_code, resp.text)
        return resp.ok, log

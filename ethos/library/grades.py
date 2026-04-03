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

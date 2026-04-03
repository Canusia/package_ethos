"""
StudentRecordsMixin — read access to a student's academic record in the SIS.

Used to verify eligibility (standing, active programs, registered courses)
before allowing enrollment through the CE workflow.
"""

import json
import logging

from urllib.parse import urlencode

from .base import EthosBase

logger = logging.getLogger(__name__)


class StudentRecordsMixin(EthosBase):
    """Read-only access to student academic records."""

    def get_student(self, person_id, **kwargs):
        """Return the core student record for a person GUID."""
        url = f'{self.URL}/api/students/{person_id}'
        accept = self.get_preferred_accept_header('students') or 'application/json'
        resp, log = self._api_request('GET', url, 'student', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_student failed: %s %s', resp.status_code, resp.text)
        return None

    def get_student_academic_periods(self, person_id, **kwargs):
        """Return the academic periods (terms) a student has been active in."""
        criteria = {'student': {'id': person_id}}
        url = f'{self.URL}/api/student-academic-periods?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('student-academic-periods') or 'application/json'
        resp, log = self._api_request('GET', url, 'student_academic_periods', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_student_academic_periods failed: %s %s', resp.status_code, resp.text)
        return []

    def get_student_academic_programs(self, person_id, **kwargs):
        """Return program enrollments for a student."""
        criteria = {'student': {'id': person_id}}
        url = f'{self.URL}/api/student-academic-programs?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('student-academic-programs') or 'application/vnd.hedtech.integration.v17+json'
        resp, log = self._api_request('GET', url, 'student_academic_programs', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_student_academic_programs failed: %s %s', resp.status_code, resp.text)
        return []

    def get_student_course_registrations(self, person_id, period_id=None, **kwargs):
        """Return registered courses for a student, optionally filtered by academic period."""
        criteria = {'registrant': {'id': person_id}}
        if period_id:
            criteria['academicPeriod'] = {'id': period_id}
        url = f'{self.URL}/api/student-course-registrations?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('student-course-registrations') or 'application/json'
        resp, log = self._api_request('GET', url, 'student_course_registrations', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_student_course_registrations failed: %s %s', resp.status_code, resp.text)
        return []

    def get_student_academic_standings(self, person_id, **kwargs):
        """Return academic standing records (GPA standing, satisfactory progress) for a student."""
        criteria = {'student': {'id': person_id}}
        url = f'{self.URL}/api/student-academic-standings?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('student-academic-standings') or 'application/json'
        resp, log = self._api_request('GET', url, 'student_academic_standings', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_student_academic_standings failed: %s %s', resp.status_code, resp.text)
        return []

    def get_enrollment_statuses(self, **kwargs):
        """Return the reference list of enrollment status codes (active, withdrawn, etc.)."""
        url = f'{self.URL}/api/enrollment-statuses'
        accept = self.get_preferred_accept_header('enrollment-statuses') or 'application/json'
        resp, log = self._api_request('GET', url, 'enrollment_statuses', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_enrollment_statuses failed: %s %s', resp.status_code, resp.text)
        return []

    def get_student_types(self, **kwargs):
        """Return the reference list of student type codes (concurrent, transfer, etc.)."""
        url = f'{self.URL}/api/student-types'
        accept = self.get_preferred_accept_header('student-types') or 'application/json'
        resp, log = self._api_request('GET', url, 'student_types', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_student_types failed: %s %s', resp.status_code, resp.text)
        return []

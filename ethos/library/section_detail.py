"""
SectionDetailMixin — satellite reads hanging off a section GUID.

Used after section import to enrich display, validate capacity,
and inspect registrations or grade types for a specific section.
"""

import json
import logging

from urllib.parse import urlencode

from .base import EthosBase

logger = logging.getLogger(__name__)


class SectionDetailMixin(EthosBase):
    """Read-only access to section-scoped sub-resources."""

    def get_section_meeting_times(self, section_id, **kwargs):
        """Return meeting time records for a section."""
        criteria = {'section': {'id': section_id}}
        url = f'{self.URL}/api/section-meeting-times?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('section-meeting-times') or 'application/json'
        resp, log = self._api_request('GET', url, 'section_meeting_times', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_section_meeting_times failed: %s %s', resp.status_code, resp.text)
        return []

    def get_section_instructors(self, section_id, **kwargs):
        """Return instructor assignment records for a section."""
        criteria = {'section': {'id': section_id}}
        url = f'{self.URL}/api/section-instructors?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('section-instructors') or 'application/json'
        resp, log = self._api_request('GET', url, 'section_instructors', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_section_instructors failed: %s %s', resp.status_code, resp.text)
        return []

    def get_section_enrollment_info(self, section_id, **kwargs):
        """Return enrollment information (capacity, enrolled, waitlist) for a section."""
        url = f'{self.URL}/api/section-enrollment-information/{section_id}'
        accept = self.get_preferred_accept_header('section-enrollment-information') or 'application/json'
        resp, log = self._api_request('GET', url, 'section_enrollment_info', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_section_enrollment_info failed: %s %s', resp.status_code, resp.text)
        return None

    def get_section_registrations(self, section_id, **kwargs):
        """Return all registration records for a section."""
        criteria = {'section': {'id': section_id}}
        url = f'{self.URL}/api/section-registrations?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('section-registrations') or 'application/vnd.hedtech.integration.v16+json'
        resp, log = self._api_request('GET', url, 'section_registrations', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_section_registrations failed: %s %s', resp.status_code, resp.text)
        return []

    def get_section_registration_statuses(self, **kwargs):
        """Return the reference list of valid section registration status codes."""
        url = f'{self.URL}/api/section-registration-statuses'
        accept = self.get_preferred_accept_header('section-registration-statuses') or 'application/json'
        resp, log = self._api_request('GET', url, 'section_registration_statuses', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_section_registration_statuses failed: %s %s', resp.status_code, resp.text)
        return []

    def get_section_grade_types(self, section_id, **kwargs):
        """Return grade types allowed for a section."""
        criteria = {'section': {'id': section_id}}
        url = f'{self.URL}/api/section-grade-types?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('section-grade-types') or 'application/json'
        resp, log = self._api_request('GET', url, 'section_grade_types', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_section_grade_types failed: %s %s', resp.status_code, resp.text)
        return []

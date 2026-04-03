"""
ReferenceMixin — slow-changing reference data used across the CE workflow.

These endpoints return small, cacheable lists used for dropdown population,
payload construction, and input validation.
"""

import json
import logging

from urllib.parse import urlencode

from .base import EthosBase

logger = logging.getLogger(__name__)


class ReferenceMixin(EthosBase):
    """Read-only access to Ethos reference / code-table data."""

    def get_academic_levels(self, **kwargs):
        """Return the list of academic levels (high school, undergrad, grad, etc.)."""
        url = f'{self.URL}/api/academic-levels'
        accept = self.get_preferred_accept_header('academic-levels') or 'application/json'
        resp, log = self._api_request('GET', url, 'academic_levels', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_academic_levels failed: %s %s', resp.status_code, resp.text)
        return []

    def get_instructional_methods(self, **kwargs):
        """Return the list of instructional methods (online, in-person, hybrid, etc.)."""
        url = f'{self.URL}/api/instructional-methods'
        accept = self.get_preferred_accept_header('instructional-methods') or 'application/json'
        resp, log = self._api_request('GET', url, 'instructional_methods', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_instructional_methods failed: %s %s', resp.status_code, resp.text)
        return []

    def get_grade_schemes(self, **kwargs):
        """Return the list of grade schemes (letter, pass/fail, numeric, etc.)."""
        url = f'{self.URL}/api/grade-schemes'
        accept = self.get_preferred_accept_header('grade-schemes') or 'application/json'
        resp, log = self._api_request('GET', url, 'grade_schemes', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_grade_schemes failed: %s %s', resp.status_code, resp.text)
        return []

    def get_academic_catalogs(self, academic_year_id=None, **kwargs):
        """Return academic catalogs, optionally filtered by academic year."""
        criteria = {}
        if academic_year_id:
            criteria['academicYear'] = {'id': academic_year_id}
        base = f'{self.URL}/api/academic-catalogs'
        url = (base + '?' + urlencode({'criteria': json.dumps(criteria)})) if criteria else base
        accept = self.get_preferred_accept_header('academic-catalogs') or 'application/json'
        resp, log = self._api_request('GET', url, 'academic_catalogs', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_academic_catalogs failed: %s %s', resp.status_code, resp.text)
        return []

    def get_educational_institution(self, institution_id, **kwargs):
        """Return a single educational institution record by its Ethos GUID."""
        url = f'{self.URL}/api/educational-institutions/{institution_id}'
        accept = self.get_preferred_accept_header('educational-institutions') or 'application/json'
        resp, log = self._api_request('GET', url, 'educational_institution', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_educational_institution failed: %s %s', resp.status_code, resp.text)
        return None

    def get_educational_institutions(self, criteria=None, **kwargs):
        """Search educational institutions by arbitrary criteria dict.

        Args:
            criteria: Optional dict, e.g. {"credentials": [{"type": "colleaguePersonId", "value": "EWU001"}]}

        Returns:
            List of institution dicts.
        """
        base = f'{self.URL}/api/educational-institutions'
        url = (base + '?' + urlencode({'criteria': json.dumps(criteria)})) if criteria else base
        accept = self.get_preferred_accept_header('educational-institutions') or 'application/json'
        resp, log = self._api_request('GET', url, 'educational_institutions', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_educational_institutions failed: %s %s', resp.status_code, resp.text)
        return []

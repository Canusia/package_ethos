"""
StudentAccountMixin — financial account reads for a student.

Used to surface balances, view prior charges, or check financial aid
status before waiving or assessing fees. Write operations live in payment.py.
"""

import json
import logging

from urllib.parse import urlencode

from .base import EthosBase

logger = logging.getLogger(__name__)


class StudentAccountMixin(EthosBase):
    """Read-only access to student financial account data."""

    def get_account_summary(self, person_id, **kwargs):
        """Return the account summary (balance due, total charges, total payments) for a student."""
        criteria = {'student': {'id': person_id}}
        url = f'{self.URL}/api/student-account-summaries?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('student-account-summaries') or 'application/json'
        resp, log = self._api_request('GET', url, 'account_summary', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            records = resp.json()
            return records[0] if records else None
        logger.error('get_account_summary failed: %s %s', resp.status_code, resp.text)
        return None

    def get_account_details(self, person_id, period_id=None, **kwargs):
        """Return line-item charges and credits for a student, optionally filtered by academic period."""
        criteria = {'student': {'id': person_id}}
        if period_id:
            criteria['academicPeriod'] = {'id': period_id}
        url = f'{self.URL}/api/student-account-details?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('student-account-details') or 'application/json'
        resp, log = self._api_request('GET', url, 'account_details', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_account_details failed: %s %s', resp.status_code, resp.text)
        return []

    def get_account_memos(self, person_id, **kwargs):
        """Return free-text account memo notes from Banner for a student."""
        criteria = {'student': {'id': person_id}}
        url = f'{self.URL}/api/student-account-memos?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('student-account-memos') or 'application/json'
        resp, log = self._api_request('GET', url, 'account_memos', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_account_memos failed: %s %s', resp.status_code, resp.text)
        return []

    def get_financial_aid_awards(self, person_id, aid_year_id=None, **kwargs):
        """Return financial aid awards for a student, optionally filtered by aid year."""
        criteria = {'student': {'id': person_id}}
        if aid_year_id:
            criteria['aidYear'] = {'id': aid_year_id}
        url = f'{self.URL}/api/student-financial-aid-awards?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('student-financial-aid-awards') or 'application/json'
        resp, log = self._api_request('GET', url, 'financial_aid_awards', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_financial_aid_awards failed: %s %s', resp.status_code, resp.text)
        return []

    def get_financial_aid_years(self, **kwargs):
        """Return the list of available financial aid years."""
        url = f'{self.URL}/api/financial-aid-years'
        accept = self.get_preferred_accept_header('financial-aid-years') or 'application/json'
        resp, log = self._api_request('GET', url, 'financial_aid_years_ref', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_financial_aid_years failed: %s %s', resp.status_code, resp.text)
        return []

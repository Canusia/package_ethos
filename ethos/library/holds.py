"""
HoldsMixin — read and release person holds.

RegistrationMixin.sendRegistrationHold handles posting a new hold.
This mixin completes the lifecycle: list, inspect, reference data, release.
"""

import json
import logging

from urllib.parse import urlencode

from .base import EthosBase

logger = logging.getLogger(__name__)


class HoldsMixin(EthosBase):
    """Read and release person holds in the SIS."""

    def get_person_holds(self, person_id, **kwargs):
        """Return all active holds for a person."""
        criteria = {'person': {'id': person_id}}
        url = f'{self.URL}/api/person-holds?' + urlencode({'criteria': json.dumps(criteria)})
        accept = self.get_preferred_accept_header('person-holds') or 'application/vnd.hedtech.integration.v6+json'
        resp, log = self._api_request('GET', url, 'person_holds', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_person_holds failed: %s %s', resp.status_code, resp.text)
        return []

    def get_person_hold(self, hold_id, **kwargs):
        """Return a single hold record by its Ethos GUID."""
        url = f'{self.URL}/api/person-holds/{hold_id}'
        accept = self.get_preferred_accept_header('person-holds') or 'application/vnd.hedtech.integration.v6+json'
        resp, log = self._api_request('GET', url, 'person_hold', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_person_hold failed: %s %s', resp.status_code, resp.text)
        return None

    def get_hold_type_codes(self, **kwargs):
        """Return the reference list of all hold type codes."""
        url = f'{self.URL}/api/hold-type-codes'
        accept = self.get_preferred_accept_header('hold-type-codes') or 'application/json'
        resp, log = self._api_request('GET', url, 'hold_type_codes', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_hold_type_codes failed: %s %s', resp.status_code, resp.text)
        return []

    def get_person_hold_types(self, **kwargs):
        """Return the reference list of person-scoped hold types."""
        url = f'{self.URL}/api/person-hold-types'
        accept = self.get_preferred_accept_header('person-hold-types') or 'application/json'
        resp, log = self._api_request('GET', url, 'person_hold_types', headers={'Accept': accept}, **kwargs)
        if resp.ok:
            return resp.json()
        logger.error('get_person_hold_types failed: %s %s', resp.status_code, resp.text)
        return []

    def release_person_hold(self, hold_id, person_id, **kwargs):
        """Release a hold by setting its endOn to today.

        Args:
            hold_id: Ethos GUID of the person-holds record.
            person_id: Ethos GUID of the person the hold belongs to.

        Returns:
            Updated hold record dict, or None on failure.
        """
        import datetime
        today = datetime.date.today().strftime('%Y-%m-%d') + 'T00:00:00Z'
        accept = self.get_preferred_accept_header('person-holds') or 'application/vnd.hedtech.integration.v6+json'
        payload = json.dumps({
            'id': hold_id,
            'person': {'id': person_id},
            'endOn': today,
        })
        url = f'{self.URL}/api/person-holds/{hold_id}'
        resp, log = self._api_request(
            'PUT', url, 'release_person_hold',
            data=payload,
            headers={
                'Accept': accept,
                'Content-Type': accept,
            },
            **kwargs,
        )
        if resp.ok:
            return resp.json()
        logger.error('release_person_hold failed: %s %s', resp.status_code, resp.text)
        return None

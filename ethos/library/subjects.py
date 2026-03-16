"""
SubjectsMixin — subjects lookup and pagination.
"""

import logging
import json

from urllib.parse import urlencode

from .base import EthosBase

logger = logging.getLogger(__name__)


class SubjectsMixin(EthosBase):
    """Subject operations: fetch, filter by abbreviation, paginate."""

    def get_subjects(self, abbreviation=None, **kwargs):
        """Fetch subjects with optional filtering and pagination.

        Args:
            abbreviation: Optional subject abbreviation filter (e.g. "MATH").
            **kwargs: Passed to _api_request (e.g. verbose=True).

        Returns:
            List of subject dicts from the Ethos API.
        """
        criteria = {}
        if abbreviation:
            criteria['abbreviation'] = abbreviation

        base_url = self.URL + '/api/subjects'
        if criteria:
            query = urlencode({'criteria': json.dumps(criteria)})
            base_url = f'{base_url}?{query}'

        all_subjects = []
        offset = 0

        while True:
            separator = '&' if '?' in base_url else '?'
            url = f'{base_url}{separator}offset={offset}'

            logger.info(f'Fetching: {url}')

            resp, sis_log = self._api_request('GET', url, 'subjects', **kwargs)

            if not resp.ok:
                logger.error(f'Failed to fetch subjects: {resp.status_code} {resp.text}')
                break

            records = resp.json()
            all_subjects.extend(records)

            total_count = resp.headers.get('x-total-count')
            page_size = int(resp.headers.get('x-max-page-size', 500))

            logger.info(f'Retrieved {len(records)} records (total so far: {len(all_subjects)}, x-total-count: {total_count})')

            if total_count is not None:
                if len(all_subjects) >= int(total_count):
                    break

            if len(records) < page_size:
                break

            offset += len(records)

        logger.info(f'Done. Total subjects fetched: {len(all_subjects)}')

        return all_subjects

    def get_subject_by_id(self, subject_id, **kwargs):
        """Fetch a single subject by its Ethos GUID.

        Args:
            subject_id: The Ethos GUID of the subject.
            **kwargs: Passed to _api_request.

        Returns:
            Subject dict or None.
        """
        url = self.URL + f'/api/subjects/{subject_id}'

        resp, sis_log = self._api_request('GET', url, 'subjects', **kwargs)

        if resp.ok:
            return resp.json()

        return None

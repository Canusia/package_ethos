"""
SectionMixin — section fetching.
"""

import logging
import json

from urllib.parse import urlencode

from .base import EthosBase

logger = logging.getLogger(__name__)


class SectionMixin(EthosBase):
    """Section operations: fetch raw sections from Ethos."""

    def get_sections(self, term_code=None, period_id=None, **kwargs):
        """Fetch all sections for a term with pagination.

        Args:
            term_code: Academic period code to filter by (looked up to get period_id).
            period_id: Academic period GUID. If provided, skips the term_code lookup.
            **kwargs: Passed to _api_request (e.g. verbose=True).

        Returns:
            List of raw section dicts from the Ethos API.
        """
        if period_id is None:
            period_id = self.get_academic_period_id(term_code)

        criteria = {'academicPeriod': {'detail': {'id': period_id}}}

        query = urlencode({'criteria': json.dumps(criteria)})
        base_url = f'{self.URL}/api/sections?{query}'

        all_sections = []
        offset = 0

        while True:
            url = f'{base_url}&offset={offset}'

            logger.info(f'Fetching: {url}')

            accept = self.get_preferred_accept_header('sections') or 'application/vnd.hedtech.integration.sections-maximum.v16+json'
            resp, sis_log = self._api_request(
                'GET', url, 'sections',
                headers={'Accept': accept},
                **kwargs,
            )

            if not resp.ok:
                logger.error(f'Failed to fetch sections for {term_code or period_id}: {resp.status_code} {resp.text}')
                break

            records = resp.json()
            all_sections.extend(records)

            total_count = resp.headers.get('x-total-count')
            page_size = int(resp.headers.get('x-max-page-size', 500))

            logger.info(f'Retrieved {len(records)} records (total so far: {len(all_sections)}, x-total-count: {total_count})')

            if total_count is not None:
                if len(all_sections) >= int(total_count):
                    break

            if len(records) < page_size:
                break

            offset += len(records)

        logger.info(f'Done. Total sections fetched: {len(all_sections)}')
        return all_sections

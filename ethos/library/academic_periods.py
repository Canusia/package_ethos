"""
AcademicPeriodsMixin — academic periods lookup and pagination.
"""

import logging
import json

from urllib.parse import urlencode

from .base import EthosBase

logger = logging.getLogger(__name__)


class AcademicPeriodsMixin(EthosBase):
    """Academic period operations: fetch, filter by code/category, paginate."""

    def get_academic_periods(self, code=None, category=None, **kwargs):
        """Fetch academic periods with optional filtering and pagination.

        Args:
            code: Optional term code filter (e.g. "2025", "23/SP").
            category: Optional category type filter ("year", "term", "subterm").
            **kwargs: Passed to _api_request (e.g. verbose=True).

        Returns:
            List of academic period dicts from the Ethos API.
        """
        criteria = {}
        if category:
            criteria['category'] = {'type': category}
        if code:
            criteria['code'] = code

        base_url = self.URL + '/api/academic-periods'
        if criteria:
            query = urlencode({'criteria': json.dumps(criteria)})
            base_url = f'{base_url}?{query}'

        all_periods = []
        offset = 0

        while True:
            separator = '&' if '?' in base_url else '?'
            url = f'{base_url}{separator}offset={offset}'

            logger.info(f'Fetching: {url}')

            resp, sis_log = self._api_request('GET', url, 'academic_period', **kwargs)

            if not resp.ok:
                logger.error(f'Failed to fetch academic periods: {resp.status_code} {resp.text}')
                break

            records = resp.json()
            all_periods.extend(records)

            total_count = resp.headers.get('x-total-count')
            page_size = int(resp.headers.get('x-max-page-size', 500))

            logger.info(f'Retrieved {len(records)} records (total so far: {len(all_periods)}, x-total-count: {total_count})')

            if total_count is not None:
                if len(all_periods) >= int(total_count):
                    break

            if len(records) < page_size:
                break

            offset += len(records)

        logger.info(f'Done. Total academic periods fetched: {len(all_periods)}')

        return all_periods

    CATEGORY_HIERARCHY = ['year', 'term', 'subterm']

    def get_child_academic_periods(self, parent, depth=2, **kwargs):
        """Return descendant academic periods for a parent period.

        Fetches each child category type via the API (which supports
        filtering by category.type), then filters client-side by
        category.parent.id to find descendants of the given parent.

        Args:
            parent: A term code (e.g. "2020") or a GUID.
            depth: How many levels deep to traverse (default 2, max 4).
            **kwargs: Passed to _api_request.

        Returns:
            List of academic period dicts (children, grandchildren, etc.).
        """
        depth = min(depth, 4)

        # Resolve parent to a full period record
        parent_period = self._resolve_academic_period(parent, **kwargs)
        if not parent_period:
            logger.error(f'Could not resolve academic period: {parent}')
            return []

        parent_id = parent_period['id']

        parent_type = parent_period.get('category', {}).get('type')
        if parent_type not in self.CATEGORY_HIERARCHY:
            logger.error(f'Unknown category type "{parent_type}" for period {parent_id}')
            return []

        start_index = self.CATEGORY_HIERARCHY.index(parent_type) + 1

        all_descendants = []
        current_parent_ids = {parent_id}

        for level in range(start_index, min(start_index + depth, len(self.CATEGORY_HIERARCHY))):
            category_type = self.CATEGORY_HIERARCHY[level]

            logger.info(f'Fetching {category_type} periods (depth level {level - start_index + 1})')

            periods = self.get_academic_periods(category=category_type, **kwargs)

            children = [
                p for p in periods
                if p.get('category', {}).get('parent', {}).get('id') in current_parent_ids
            ]

            if not children:
                break

            all_descendants.extend(children)
            current_parent_ids = {c['id'] for c in children}

        logger.info(f'Found {len(all_descendants)} descendant periods for {parent_id}')

        return all_descendants

    def _is_guid(self, value):
        """Check if a string looks like a UUID/GUID."""
        import re
        return bool(re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', value, re.IGNORECASE))

    def _resolve_academic_period(self, value, **kwargs):
        """Resolve a code or GUID to a full academic period record."""
        if self._is_guid(value):
            url = self.URL + f'/api/academic-periods/{value}'
            resp, sis_log = self._api_request('GET', url, 'academic_period', **kwargs)
            if resp.ok:
                return resp.json()
            return None

        # Treat as a code
        periods = self.get_academic_periods(code=value, **kwargs)
        if periods:
            return periods[0]
        return None

    def get_academic_period_id(self, code='23/SP'):
        """Look up an academic period GUID by term code."""
        periods = self.get_academic_periods(code=code)
        if periods:
            return str(periods[0].get('id'))
        return None

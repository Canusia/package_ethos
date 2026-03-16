"""
CoursesMixin — courses lookup and pagination.
"""

import logging
import json

from urllib.parse import urlencode

from .base import EthosBase

logger = logging.getLogger(__name__)


class CoursesMixin(EthosBase):
    """Course operations: fetch, filter by number/title, paginate."""

    def get_courses(self, number=None, title=None, **kwargs):
        """Fetch courses with optional filtering and pagination.

        Args:
            number: Optional course number filter.
            title: Optional course title filter.
            **kwargs: Passed to _api_request (e.g. verbose=True).

        Returns:
            List of course dicts from the Ethos API.
        """
        criteria = {}
        if number:
            criteria['number'] = number
        if title:
            criteria['title'] = title

        base_url = self.URL + '/api/courses'
        if criteria:
            query = urlencode({'criteria': json.dumps(criteria)})
            base_url = f'{base_url}?{query}'

        all_courses = []
        offset = 0

        while True:
            separator = '&' if '?' in base_url else '?'
            url = f'{base_url}{separator}offset={offset}'

            logger.info(f'Fetching: {url}')

            resp, sis_log = self._api_request('GET', url, 'courses', **kwargs)

            if not resp.ok:
                logger.error(f'Failed to fetch courses: {resp.status_code} {resp.text}')
                break

            records = resp.json()
            all_courses.extend(records)

            total_count = resp.headers.get('x-total-count')
            page_size = int(resp.headers.get('x-max-page-size', 500))

            logger.info(f'Retrieved {len(records)} records (total so far: {len(all_courses)}, x-total-count: {total_count})')

            if total_count is not None:
                if len(all_courses) >= int(total_count):
                    break

            if len(records) < page_size:
                break

            offset += len(records)

        logger.info(f'Done. Total courses fetched: {len(all_courses)}')

        return all_courses

    def get_course_by_id(self, course_id, **kwargs):
        """Fetch a single course by its Ethos GUID.

        Args:
            course_id: The Ethos GUID of the course.
            **kwargs: Passed to _api_request.

        Returns:
            Course dict or None.
        """
        url = self.URL + f'/api/courses/{course_id}'

        resp, sis_log = self._api_request('GET', url, 'courses', **kwargs)

        if resp.ok:
            return resp.json()

        return None

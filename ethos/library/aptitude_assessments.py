"""
AptitudeAssessmentsMixin — the aptitude assessment (test) catalog.

`aptitude-assessments` is the definition of a test (ACT Composite, SAT
Mathematics, a local math placement).  Colleague sources it from NON.COURSES
where the category represents a test.  Scores themselves live in the separate
`student-aptitude-assessments` resource, which references these records only by
GUID — so anything that displays a score needs this catalog to turn that GUID
into a name.
"""

import logging

from .base import EthosBase

logger = logging.getLogger(__name__)

RESOURCE = 'aptitude-assessments'


class AptitudeAssessmentsMixin(EthosBase):
    """Read the assessment catalog."""

    def get_aptitude_assessments(self, accept=None, **kwargs):
        """Fetch every aptitude assessment, following pagination.

        Args:
            accept: Optional Accept header override.
            **kwargs: Passed to _api_request (e.g. verbose=True).

        Returns:
            List of assessment dicts; empty list on error.
        """
        headers = {'Accept': self._resolve_accept(RESOURCE, accept)}
        base_url = self.URL + f'/api/{RESOURCE}'

        all_records = []
        offset = 0

        while True:
            separator = '&' if '?' in base_url else '?'
            url = f'{base_url}{separator}offset={offset}'

            resp, log = self._api_request(
                'GET', url, 'aptitude_assessments', headers=headers, **kwargs)

            if not resp.ok:
                logger.error('get_aptitude_assessments failed: %s %s',
                             resp.status_code, resp.text)
                break

            records = resp.json()
            all_records.extend(records)

            total_count = resp.headers.get('x-total-count')
            page_size = int(resp.headers.get('x-max-page-size', 500))

            if total_count is not None and len(all_records) >= int(total_count):
                break

            if len(records) < page_size:
                break

            offset += len(records)

        return all_records

    def get_aptitude_assessment_by_id(self, assessment_id, accept=None, **kwargs):
        """Fetch a single aptitude assessment by its Ethos GUID.

        Returns:
            Assessment dict, or None if not found.
        """
        headers = {'Accept': self._resolve_accept(RESOURCE, accept)}
        url = self.URL + f'/api/{RESOURCE}/{assessment_id}'

        resp, log = self._api_request(
            'GET', url, 'aptitude_assessment', headers=headers, **kwargs)

        if resp.ok:
            return resp.json()

        logger.error('get_aptitude_assessment_by_id failed: %s %s',
                     resp.status_code, resp.text)
        return None

    def get_aptitude_assessment_map(self, refresh=False, **kwargs):
        """Return {guid: assessment} for the whole catalog.

        Cached on the client instance: resolving a page of scores would
        otherwise re-fetch the catalog once per score.  Pass refresh=True to
        force a re-fetch.
        """
        cached = getattr(self, '_aptitude_assessment_map', None)
        if cached is not None and not refresh:
            return cached

        records = self.get_aptitude_assessments(**kwargs)
        mapping = {r['id']: r for r in records if r.get('id')}
        self._aptitude_assessment_map = mapping
        return mapping

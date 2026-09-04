"""
StudentAptitudeAssessmentsMixin — student test scores.

`student-aptitude-assessments` is Colleague's STUDENT.NON.COURSES: one record
per student x assessment x sitting.  Full CRUD, per the Ellucian OpenAPI spec
v16.2.0.

Three things in that spec shape this module:

* `score` is a `oneOf` of literal and numeric, but Colleague marks literal
  unsupported, so writes always send `numeric`.
* `update` (original/revised/recentered) is likewise unsupported by Colleague,
  so it is never written.
* status / reported / preference are each `oneOf [enum, maxLength: 0]` — the
  empty string is a legal value on read, so nothing may assume an enum member.

Colleague permissions: VIEW.STUDENT.TEST.SCORES to read,
UPDATE.STUDENT.TEST.SCORES to create/update, DELETE.STUDENT.TEST.SCORES to
delete.  A 403 from these methods usually means the integration user lacks the
permission rather than that the call was malformed.
"""

import json
import logging

from urllib.parse import urlencode

from .base import EthosBase

logger = logging.getLogger(__name__)

RESOURCE = 'student-aptitude-assessments'

#: POST requires the nil GUID as the root id (spec: "POST requests must include
#: a nil GUID value for the root id property").
NIL_GUID = '00000000-0000-0000-0000-000000000000'

DEFAULT_ACCEPT = 'application/vnd.hedtech.integration.v16+json'


def _validate_percentiles(percentiles):
    """Raise ValueError for percentile lists the API would reject.

    The spec forbids duplicate percentiles.type and values above 100.  Catching
    it here turns a 400 with an opaque body into a clear local error.
    """
    if not percentiles:
        return

    seen = set()
    for entry in percentiles:
        value = entry.get('value')
        if value is not None and float(value) > 100:
            raise ValueError(
                f'percentile value {value} exceeds 100; the API will reject it')

        type_id = (entry.get('type') or {}).get('id')
        if type_id is None:
            continue
        if type_id in seen:
            raise ValueError(
                f'duplicate percentile type {type_id}; the API will reject it')
        seen.add(type_id)


def _as_date_string(value):
    """Return an ISO date string for a date/datetime, or the value unchanged."""
    isoformat = getattr(value, 'isoformat', None)
    if isoformat is None:
        return value
    return isoformat()[:10]


def _blank_to_none(value):
    """Normalise the spec's empty-string-instead-of-enum to None."""
    return value or None


class StudentAptitudeAssessmentsMixin(EthosBase):
    """Read and write student test scores."""

    # ── read ──

    def get_student_aptitude_assessments(self, student_id=None, assessment_id=None,
                                         accept=None, **kwargs):
        """Fetch score records, optionally filtered, following pagination.

        Args:
            student_id: Optional Ethos person GUID (Student.sis_id).
            assessment_id: Optional aptitude-assessment GUID.
            accept: Optional Accept header override.

        Returns:
            List of score dicts; empty list on error.
        """
        headers = {'Accept': self._resolve_accept(RESOURCE, accept, DEFAULT_ACCEPT)}

        criteria = {}
        if student_id:
            criteria['student'] = {'id': str(student_id)}
        if assessment_id:
            criteria['assessment'] = {'id': str(assessment_id)}

        base_url = self.URL + f'/api/{RESOURCE}'
        if criteria:
            base_url = f'{base_url}?' + urlencode({'criteria': json.dumps(criteria)})

        all_records = []
        offset = 0

        while True:
            separator = '&' if '?' in base_url else '?'
            url = f'{base_url}{separator}offset={offset}'

            resp, log = self._api_request(
                'GET', url, 'student_aptitude_assessments', headers=headers, **kwargs)

            if not resp.ok:
                logger.error('get_student_aptitude_assessments failed: %s %s',
                             resp.status_code, resp.text)
                break

            records = resp.json()
            all_records.extend(records)

            total_count = resp.headers.get('x-total-count')
            # The spec caps this resource's page size at 200.
            page_size = int(resp.headers.get('x-max-page-size', 200))

            if total_count is not None and len(all_records) >= int(total_count):
                break

            if len(records) < page_size:
                break

            offset += len(records)

        return all_records

    def get_student_aptitude_assessment(self, record_id, accept=None, **kwargs):
        """Fetch a single score record by its Ethos GUID, or None."""
        headers = {'Accept': self._resolve_accept(RESOURCE, accept, DEFAULT_ACCEPT)}
        url = self.URL + f'/api/{RESOURCE}/{record_id}'

        resp, log = self._api_request(
            'GET', url, 'student_aptitude_assessment', headers=headers, **kwargs)

        if resp.ok:
            return resp.json()

        logger.error('get_student_aptitude_assessment failed: %s %s',
                     resp.status_code, resp.text)
        return None

    def get_student_scores_resolved(self, student_id, **kwargs):
        """Return a student's scores with the assessment GUIDs resolved to names.

        A raw score record identifies its assessment only by GUID, so on its own
        it cannot say whether it is an ACT composite or a local placement test.
        This joins each record against the assessment catalog and flattens the
        polymorphic score into plain fields.

        Returns:
            List of dicts with id, assessment_id/code/title, assessed_on, score,
            score_type, status, reported, preference, percentiles, comment and
            the untouched record under 'raw'.
        """
        records = self.get_student_aptitude_assessments(student_id=student_id, **kwargs)
        if not records:
            return []

        catalog = self.get_aptitude_assessment_map(**kwargs)

        rows = []
        for record in records:
            assessment_id = (record.get('assessment') or {}).get('id')
            assessment = catalog.get(assessment_id) or {}
            score = record.get('score') or {}

            rows.append({
                'id': record.get('id'),
                'assessment_id': assessment_id,
                'assessment_code': assessment.get('code'),
                'assessment_title': assessment.get('title'),
                'assessed_on': record.get('assessedOn'),
                'score': score.get('value'),
                'score_type': score.get('type'),
                'status': _blank_to_none(record.get('status')),
                'reported': _blank_to_none(record.get('reported')),
                'preference': _blank_to_none(record.get('preference')),
                'percentiles': record.get('percentiles') or [],
                'override_title': record.get('overrideTitle'),
                'comment': record.get('comment'),
                'raw': record,
            })

        return rows

    # ── write ──

    def create_student_aptitude_assessment(
            self, student_id, assessment_id, assessed_on, score_value,
            percentiles=None, form=None, special_circumstances=None,
            source_id=None, reported=None, preference=None,
            override_title=None, comment=None, accept=None, **kwargs):
        """Create a score record (POST).

        Args:
            student_id: Ethos person GUID.
            assessment_id: aptitude-assessment GUID.
            assessed_on: date or 'YYYY-MM-DD' string.
            score_value: numeric score; must fall within the assessment's
                NCRS.MIN.SCORE / NCRS.MAX.SCORE or the API rejects it.
            percentiles: list of {'value': n, 'type': {'id': guid}}.
            special_circumstances: list of GUID strings.
            source_id: sources GUID.

        `status` is deliberately omitted (the spec says to omit it on create)
        and `update` is never sent (Colleague does not support it).

        Returns:
            The created record dict, or None on failure.
        """
        _validate_percentiles(percentiles)

        payload = {
            'id': NIL_GUID,
            'student': {'id': str(student_id)},
            'assessment': {'id': str(assessment_id)},
            'assessedOn': _as_date_string(assessed_on),
            'score': {'type': 'numeric', 'value': float(score_value)},
        }

        if percentiles:
            payload['percentiles'] = percentiles
        if form:
            payload['form'] = form
        if special_circumstances:
            payload['specialCircumstances'] = [{'id': str(s)} for s in special_circumstances]
        if source_id:
            payload['source'] = {'id': str(source_id)}
        if reported:
            payload['reported'] = reported
        if preference:
            payload['preference'] = preference
        if override_title:
            payload['overrideTitle'] = override_title
        if comment:
            payload['comment'] = comment

        content_type = self._resolve_accept(RESOURCE, accept, DEFAULT_ACCEPT)
        url = self.URL + f'/api/{RESOURCE}'

        resp, log = self._api_request(
            'POST', url, 'create_student_aptitude_assessment',
            data=json.dumps(payload),
            headers={'Accept': content_type, 'Content-Type': content_type},
            **kwargs)

        if resp.ok:
            return resp.json()

        logger.error('create_student_aptitude_assessment failed: %s %s',
                     resp.status_code, resp.text)
        return None

    def update_student_aptitude_assessment(self, record_id, payload,
                                           accept=None, **kwargs):
        """Replace a score record (PUT).

        The root id is forced to match record_id so a payload copied from a
        different record cannot silently retarget the write.

        Returns:
            The updated record dict, or None on failure.
        """
        payload = dict(payload or {})
        payload['id'] = str(record_id)

        _validate_percentiles(payload.get('percentiles'))

        content_type = self._resolve_accept(RESOURCE, accept, DEFAULT_ACCEPT)
        url = self.URL + f'/api/{RESOURCE}/{record_id}'

        resp, log = self._api_request(
            'PUT', url, 'update_student_aptitude_assessment',
            data=json.dumps(payload),
            headers={'Accept': content_type, 'Content-Type': content_type},
            **kwargs)

        if resp.ok:
            return resp.json()

        logger.error('update_student_aptitude_assessment failed: %s %s',
                     resp.status_code, resp.text)
        return None

    def delete_student_aptitude_assessment(self, record_id, **kwargs):
        """Delete a score record (DELETE).

        The API refuses to delete a record that has related equivalencies or
        subtest components; that surfaces here as False.

        Returns:
            True on success (204), False otherwise.
        """
        url = self.URL + f'/api/{RESOURCE}/{record_id}'

        resp, log = self._api_request(
            'DELETE', url, 'delete_student_aptitude_assessment', **kwargs)

        if resp.ok:
            return True

        logger.error('delete_student_aptitude_assessment failed: %s %s',
                     resp.status_code, resp.text)
        return False

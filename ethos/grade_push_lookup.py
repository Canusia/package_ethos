"""Read-only Banner look-ups behind the "Banner Grade Push" setting.

A sample section registration gives the exact grade options of its grade
scheme (``grade-schemes`` is 403 for EWU's key and ``grade-definitions``
ignores the scheme filter), its section (for the instructors offered as
submitted-by) and the scheme's name. ``primary_instructor`` is also used at
push time when submittedBy is the section's primary instructor.
"""
import json
import logging
from urllib.parse import urlencode

from .grade_push import _grade_scale
from .grade_push_config import load

logger = logging.getLogger(__name__)

GRADE_OPTIONS_ACCEPT = (
    'application/vnd.hedtech.integration.section-registrations-grade-options.v1+json')


class BannerLookupError(Exception):
    def __init__(self, status=0, log=None, what='', detail=''):
        self.status = status
        self.log = log
        msg = f'Banner {what} look-up failed'
        if status:
            msg += f' (HTTP {status})'
        if detail:
            msg += f': {detail}'
        super().__init__(msg + '.')


class SubmitterError(Exception):
    """Banner does not name exactly one primary instructor to submit the grade."""


def _get(client, path, message_type, expect, accept='application/json'):
    """GET a Banner JSON body of type `expect` (dict or list), or raise BannerLookupError."""
    what = message_type.replace('grade_push_', '').replace('_', ' ')
    try:
        resp, log = client._api_request(
            'GET', f'{client.URL}/api/{path}', message_type, headers={'Accept': accept})
    except Exception as exc:
        logger.warning('Banner %s look-up failed: %r', what, exc)
        raise BannerLookupError(0, None, what, str(exc) or type(exc).__name__) from exc
    if not resp.ok:
        raise BannerLookupError(resp.status_code, log, what)
    try:
        body = resp.json()
    except ValueError as exc:
        raise BannerLookupError(resp.status_code, log, what, 'response was not valid JSON') from exc
    if not isinstance(body, expect):
        raise BannerLookupError(resp.status_code, log, what, 'unexpected response shape')
    return body


def grade_options(client, registration_id):
    data = _get(client, f'section-registrations/{registration_id}',
                'grade_push_grade_options', dict, GRADE_OPTIONS_ACCEPT)
    scheme = data.get('studentGradeScheme') or {}
    return {
        'section': (data.get('section') or {}).get('id') or '',
        'scheme': {'id': (scheme.get('detail') or {}).get('id') or '',
                   'title': scheme.get('title') or ''},
        'grades': [{'value': g.get('value') or '', 'id': (g.get('grade') or {}).get('id') or ''}
                   for g in data.get('grades') or []],
    }


def _person_name(client, person_id):
    try:
        resp, _log = client._api_request(
            'GET', f'{client.URL}/api/persons/{person_id}', 'grade_push_person',
            headers={'Accept': 'application/json'})
        if not resp.ok:
            return person_id
        names = resp.json().get('names') or []
    except Exception:
        return person_id
    preferred = next((n for n in names if n.get('preference') == 'preferred'),
                     names[0] if names else {})
    return preferred.get('fullName') or person_id


def section_instructors(client, section_id):
    """The section's instructors as [{'id': person guid, 'role': instructorRole}]."""
    query = urlencode({'criteria': json.dumps({'section': {'id': section_id}})})
    rows = _get(client, f'section-instructors?{query}', 'grade_push_instructors', list)
    return [{'id': (row.get('instructor') or {}).get('id'), 'role': row.get('instructorRole') or ''}
            for row in rows if isinstance(row, dict) and (row.get('instructor') or {}).get('id')]


def primary_instructor(client, registration_id):
    """The Banner person GUID of the primary instructor of the registration's section.

    Raises SubmitterError unless Banner lists exactly one primary instructor
    (a wrong submitter on a grade is worse than a visible failure), and
    BannerLookupError when a Banner call fails.
    """
    section = grade_options(client, registration_id)['section']
    if not section:
        raise SubmitterError('Banner returned no section for this registration.')
    primaries = [i['id'] for i in section_instructors(client, section)
                 if i['role'].lower() == 'primary']
    if not primaries:
        raise SubmitterError('Section has no primary instructor in Banner.')
    if len(primaries) > 1:
        raise SubmitterError(
            f'Section has {len(primaries)} primary instructors in Banner; expected one.')
    return primaries[0]


def lookup(client, registration_id):
    options = grade_options(client, registration_id)
    types = _get(client, 'section-grade-types', 'grade_push_grade_types', list)
    instructors = []
    if options['section']:
        for row in section_instructors(client, options['section']):
            instructors.append({'id': row['id'], 'name': _person_name(client, row['id']),
                                'role': row['role']})
    return {
        'registration': registration_id,
        'section': options['section'],
        'scheme': options['scheme'],
        'grade_options': options['grades'],
        'grade_types': [{'id': t.get('id'), 'code': t.get('code') or '', 'title': t.get('title') or ''}
                        for t in types],
        'instructors': instructors,
        'scale': _grade_scale(),
        'current': load(),
    }

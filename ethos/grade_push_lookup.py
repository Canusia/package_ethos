"""Read-only Banner look-ups behind the "Banner Grade Push" setting.

A sample section registration gives the exact grade options of its grade
scheme (``grade-schemes`` is 403 for EWU's key and ``grade-definitions``
ignores the scheme filter), its section (for the instructors offered as
submitted-by) and the scheme's name.
"""
import json
from urllib.parse import urlencode

from .grade_push import _grade_scale
from .grade_push_config import load

GRADE_OPTIONS_ACCEPT = (
    'application/vnd.hedtech.integration.section-registrations-grade-options.v1+json')


class BannerLookupError(Exception):
    def __init__(self, status, log=None, what=''):
        self.status = status
        self.log = log
        super().__init__(f'Banner {what} look-up failed (HTTP {status}).')


def _get(client, path, message_type, accept='application/json'):
    resp, log = client._api_request(
        'GET', f'{client.URL}/api/{path}', message_type, headers={'Accept': accept})
    if not resp.ok:
        raise BannerLookupError(resp.status_code, log, message_type.replace('_', ' '))
    return resp.json()


def grade_options(client, registration_id):
    data = _get(client, f'section-registrations/{registration_id}',
                'grade_push_grade_options', GRADE_OPTIONS_ACCEPT)
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


def lookup(client, registration_id):
    options = grade_options(client, registration_id)
    types = _get(client, 'section-grade-types', 'grade_push_grade_types')
    instructors = []
    if options['section']:
        query = urlencode({'criteria': json.dumps({'section': {'id': options['section']}})})
        for row in _get(client, f'section-instructors?{query}', 'grade_push_instructors'):
            person = (row.get('instructor') or {}).get('id')
            if person:
                instructors.append({'id': person, 'name': _person_name(client, person),
                                    'role': row.get('instructorRole') or ''})
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

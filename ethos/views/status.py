"""
Ethos API Explorer — status page and method runner.
"""

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from ..library.ethos import Ethos


_PAGINATION_PARAMS = [
    {'name': 'offset', 'type': 'int', 'required': False, 'placeholder': 'e.g. 0'},
    {'name': 'limit', 'type': 'int', 'required': False, 'placeholder': 'e.g. 25'},
]

METHOD_REGISTRY = {
    'academic_periods': {
        'label': 'Academic Periods',
        'methods': {
            'get_academic_periods': {
                'doc': (
                    'Fetch academic periods with optional filtering. '
                    'Leave both blank to retrieve all periods. '
                    'category must be one of: year, term, subterm.'
                ),
                'params': [
                    {'name': 'code', 'type': 'str', 'required': False, 'placeholder': 'e.g. 202620'},
                    {'name': 'category', 'type': 'str', 'required': False, 'placeholder': 'year / term / subterm'},
                ] + _PAGINATION_PARAMS,
            },
            'get_academic_period_id': {
                'doc': 'Look up an academic period GUID by term code. Returns a GUID string.',
                'params': [
                    {'name': 'code', 'type': 'str', 'required': True, 'placeholder': 'e.g. 202620'},
                ] + _PAGINATION_PARAMS,
            },
            'get_child_academic_periods': {
                'doc': (
                    'Return descendant academic periods for a parent period. '
                    'parent can be a term code (e.g. "2026") or a GUID. '
                    'depth controls how many levels deep to traverse (default 2).'
                ),
                'params': [
                    {'name': 'parent', 'type': 'str', 'required': True, 'placeholder': 'e.g. 2026 or a GUID'},
                    {'name': 'depth', 'type': 'int', 'required': False, 'placeholder': 'default 2'},
                ] + _PAGINATION_PARAMS,
            },
        },
    },
    'subjects': {
        'label': 'Subjects',
        'methods': {
            'get_subjects': {
                'doc': (
                    'Fetch subjects with optional filtering. '
                    'Leave abbreviation blank to retrieve all subjects.'
                ),
                'params': [
                    {'name': 'abbreviation', 'type': 'str', 'required': False, 'placeholder': 'e.g. MATH'},
                ] + _PAGINATION_PARAMS,
            },
            'get_subject_by_id': {
                'doc': 'Fetch a single subject by its Ethos GUID.',
                'params': [
                    {'name': 'subject_id', 'type': 'str', 'required': True, 'placeholder': 'Ethos GUID'},
                ] + _PAGINATION_PARAMS,
            },
        },
    },
    'courses': {
        'label': 'Courses',
        'methods': {
            'get_courses': {
                'doc': (
                    'Fetch courses with optional filtering. '
                    'Leave both blank to retrieve all courses (may be large).'
                ),
                'params': [
                    {'name': 'number', 'type': 'str', 'required': False, 'placeholder': 'e.g. 101'},
                    {'name': 'title', 'type': 'str', 'required': False, 'placeholder': 'e.g. Calculus'},
                ] + _PAGINATION_PARAMS,
            },
            'get_course_by_id': {
                'doc': 'Fetch a single course by its Ethos GUID.',
                'params': [
                    {'name': 'course_id', 'type': 'str', 'required': True, 'placeholder': 'Ethos GUID'},
                ] + _PAGINATION_PARAMS,
            },
        },
    },
    'sections': {
        'label': 'Sections',
        'methods': {
            'get_sections': {
                'doc': (
                    'Fetch all sections for a term. Provide either term_code (e.g. 202620) '
                    'or period_id (GUID). '
                    'WARNING: This can return hundreds of records. Use limit to cap results.'
                ),
                'params': [
                    {'name': 'term_code', 'type': 'str', 'required': False, 'placeholder': 'e.g. 202620'},
                    {'name': 'period_id', 'type': 'str', 'required': False, 'placeholder': 'Academic period GUID'},
                ] + _PAGINATION_PARAMS,
            },
        },
    },
    'sites_programs': {
        'label': 'Sites & Programs',
        'methods': {
            'get_sites': {
                'doc': 'List all available sites from Ethos. No parameters required.',
                'params': [] + _PAGINATION_PARAMS,
            },
            'get_academic_programs': {
                'doc': 'List academic programs, optionally filtered by code.',
                'params': [
                    {'name': 'code', 'type': 'str', 'required': False, 'placeholder': 'e.g. CE'},
                ] + _PAGINATION_PARAMS,
            },
        },
    },
    'person': {
        'label': 'Person',
        'methods': {
            'get_person': {
                'doc': (
                    'Retrieve a person record by Ethos person ID (GUID). '
                    'Returns Banner ID and email extracted from the record.'
                ),
                'params': [
                    {'name': 'personid', 'type': 'str', 'required': True, 'placeholder': 'Ethos person GUID'},
                ] + _PAGINATION_PARAMS,
            },
        },
    },
    'admin': {
        'label': 'Admin',
        'methods': {
            'get_available_resources': {
                'doc': (
                    'List all Ethos applications and their available API resources. '
                    'Returns each application with its name, version info, and the '
                    'resources it exposes (including supported HTTP methods and media types). '
                    'No parameters required.'
                ),
                'params': [] + _PAGINATION_PARAMS,
            },
        },
    },
}

# Flat allowlist of permitted method names
_ALLOWED_METHODS = {
    method_name
    for group in METHOD_REGISTRY.values()
    for method_name in group['methods']
}

# Int params that need type coercion
_INT_PARAMS = {'depth', 'offset', 'limit'}


@require_GET
def status_page(request):
    registry_json = json.dumps(METHOD_REGISTRY)
    return render(request, 'ethos/status.html', {
        'registry_json': registry_json,
        'registry': METHOD_REGISTRY,
    })


@require_POST
def run_method(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        body = request.POST.dict()

    method_name = body.get('method_name') or body.get('method', '')
    raw_params = body.get('params', {})

    if method_name not in _ALLOWED_METHODS:
        return JsonResponse({'error': f'Method "{method_name}" is not in the allowed list.'}, status=400)

    # Strip empty strings; coerce int params; separate pagination from method kwargs
    kwargs = {}
    offset = None
    limit = None
    for k, v in raw_params.items():
        if v == '' or v is None:
            continue
        if k in _INT_PARAMS:
            try:
                coerced = int(v)
            except (ValueError, TypeError):
                coerced = v
            if k == 'offset':
                offset = coerced
            elif k == 'limit':
                limit = coerced
            else:
                kwargs[k] = coerced
        else:
            kwargs[k] = v

    try:
        ethos = Ethos()
        method = getattr(ethos, method_name)
        result = method(**kwargs)
        if isinstance(result, list):
            start = offset or 0
            result = result[start:start + limit] if limit is not None else result[start:]
        return JsonResponse({'result': result}, status=200, safe=False, json_dumps_params={'default': str})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

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
    'section_detail': {
        'label': 'Section Detail',
        'methods': {
            'get_section_meeting_times': {
                'doc': 'Return meeting time records for a section GUID.',
                'params': [
                    {'name': 'section_id', 'type': 'str', 'required': True, 'placeholder': 'Section Ethos GUID'},
                ],
            },
            'get_section_instructors': {
                'doc': 'Return instructor assignment records for a section GUID.',
                'params': [
                    {'name': 'section_id', 'type': 'str', 'required': True, 'placeholder': 'Section Ethos GUID'},
                ],
            },
            'get_section_enrollment_info': {
                'doc': 'Return enrollment information (capacity, enrolled count, waitlist) for a section GUID.',
                'params': [
                    {'name': 'section_id', 'type': 'str', 'required': True, 'placeholder': 'Section Ethos GUID'},
                ],
            },
            'get_section_registrations': {
                'doc': 'Return all registration records for a section GUID.',
                'params': [
                    {'name': 'section_id', 'type': 'str', 'required': True, 'placeholder': 'Section Ethos GUID'},
                ] + _PAGINATION_PARAMS,
            },
            'get_section_registration_statuses': {
                'doc': 'Return the reference list of valid section registration status codes.',
                'params': [] + _PAGINATION_PARAMS,
            },
            'get_section_grade_types': {
                'doc': 'Return grade types allowed for a section GUID.',
                'params': [
                    {'name': 'section_id', 'type': 'str', 'required': True, 'placeholder': 'Section Ethos GUID'},
                ],
            },
        },
    },
    'student_records': {
        'label': 'Student Records',
        'methods': {
            'get_student': {
                'doc': 'Return the core student record for a person GUID.',
                'params': [
                    {'name': 'person_id', 'type': 'str', 'required': True, 'placeholder': 'Person Ethos GUID'},
                ],
            },
            'get_student_academic_periods': {
                'doc': 'Return the academic periods (terms) a student has been active in.',
                'params': [
                    {'name': 'person_id', 'type': 'str', 'required': True, 'placeholder': 'Person Ethos GUID'},
                ] + _PAGINATION_PARAMS,
            },
            'get_student_academic_programs': {
                'doc': 'Return program enrollments for a student.',
                'params': [
                    {'name': 'person_id', 'type': 'str', 'required': True, 'placeholder': 'Person Ethos GUID'},
                ] + _PAGINATION_PARAMS,
            },
            'get_student_course_registrations': {
                'doc': 'Return registered courses for a student. Optionally filter by academic period GUID.',
                'params': [
                    {'name': 'person_id', 'type': 'str', 'required': True, 'placeholder': 'Person Ethos GUID'},
                    {'name': 'period_id', 'type': 'str', 'required': False, 'placeholder': 'Academic period GUID (optional)'},
                ] + _PAGINATION_PARAMS,
            },
            'get_student_academic_standings': {
                'doc': 'Return academic standing records (GPA standing, satisfactory progress) for a student.',
                'params': [
                    {'name': 'person_id', 'type': 'str', 'required': True, 'placeholder': 'Person Ethos GUID'},
                ] + _PAGINATION_PARAMS,
            },
            'get_enrollment_statuses': {
                'doc': 'Return the reference list of enrollment status codes (active, withdrawn, etc.).',
                'params': [] + _PAGINATION_PARAMS,
            },
            'get_student_types': {
                'doc': 'Return the reference list of student type codes (concurrent, transfer, etc.).',
                'params': [] + _PAGINATION_PARAMS,
            },
        },
    },
    'student_account': {
        'label': 'Student Account',
        'methods': {
            'get_account_summary': {
                'doc': 'Return the account summary (balance due, charges, payments) for a student.',
                'params': [
                    {'name': 'person_id', 'type': 'str', 'required': True, 'placeholder': 'Person Ethos GUID'},
                ],
            },
            'get_account_details': {
                'doc': 'Return line-item charges and credits for a student. Optionally filter by academic period.',
                'params': [
                    {'name': 'person_id', 'type': 'str', 'required': True, 'placeholder': 'Person Ethos GUID'},
                    {'name': 'period_id', 'type': 'str', 'required': False, 'placeholder': 'Academic period GUID (optional)'},
                ] + _PAGINATION_PARAMS,
            },
            'get_account_memos': {
                'doc': 'Return free-text account memo notes from Banner for a student.',
                'params': [
                    {'name': 'person_id', 'type': 'str', 'required': True, 'placeholder': 'Person Ethos GUID'},
                ] + _PAGINATION_PARAMS,
            },
            'get_financial_aid_awards': {
                'doc': 'Return financial aid awards for a student. Optionally filter by aid year GUID.',
                'params': [
                    {'name': 'person_id', 'type': 'str', 'required': True, 'placeholder': 'Person Ethos GUID'},
                    {'name': 'aid_year_id', 'type': 'str', 'required': False, 'placeholder': 'Aid year GUID (optional)'},
                ] + _PAGINATION_PARAMS,
            },
            'get_financial_aid_years': {
                'doc': 'Return the list of available financial aid years.',
                'params': [] + _PAGINATION_PARAMS,
            },
        },
    },
    'grades': {
        'label': 'Grades',
        'methods': {
            'get_student_grades': {
                'doc': 'Return grade records for a student. Optionally filter by academic period GUID.',
                'params': [
                    {'name': 'person_id', 'type': 'str', 'required': True, 'placeholder': 'Person Ethos GUID'},
                    {'name': 'period_id', 'type': 'str', 'required': False, 'placeholder': 'Academic period GUID (optional)'},
                ] + _PAGINATION_PARAMS,
            },
            'get_grade_definitions': {
                'doc': 'Return valid grade values (A, B, C, …). Optionally scoped to a grade scheme GUID.',
                'params': [
                    {'name': 'grade_scheme_id', 'type': 'str', 'required': False, 'placeholder': 'Grade scheme GUID (optional)'},
                ] + _PAGINATION_PARAMS,
            },
            'get_grade_modes': {
                'doc': 'Return the reference list of grading modes (standard, audit, pass/fail, etc.).',
                'params': [] + _PAGINATION_PARAMS,
            },
            'get_student_gpa': {
                'doc': 'Return cumulative and period GPA records for a student.',
                'params': [
                    {'name': 'person_id', 'type': 'str', 'required': True, 'placeholder': 'Person Ethos GUID'},
                ] + _PAGINATION_PARAMS,
            },
            'get_section_grade_types': {
                'doc': 'Return the grade types that apply to a specific section GUID.',
                'params': [
                    {'name': 'section_id', 'type': 'str', 'required': True, 'placeholder': 'Section Ethos GUID'},
                ],
            },
        },
    },
    'holds': {
        'label': 'Holds',
        'methods': {
            'get_person_holds': {
                'doc': 'Return all active holds for a person GUID.',
                'params': [
                    {'name': 'person_id', 'type': 'str', 'required': True, 'placeholder': 'Person Ethos GUID'},
                ] + _PAGINATION_PARAMS,
            },
            'get_person_hold': {
                'doc': 'Return a single hold record by its Ethos GUID.',
                'params': [
                    {'name': 'hold_id', 'type': 'str', 'required': True, 'placeholder': 'Hold Ethos GUID'},
                ],
            },
            'get_hold_type_codes': {
                'doc': 'Return the reference list of all hold type codes.',
                'params': [] + _PAGINATION_PARAMS,
            },
            'get_person_hold_types': {
                'doc': 'Return the reference list of person-scoped hold types.',
                'params': [] + _PAGINATION_PARAMS,
            },
        },
    },
    'reference': {
        'label': 'Reference Data',
        'methods': {
            'get_academic_levels': {
                'doc': 'Return the list of academic levels (high school, undergrad, grad, etc.).',
                'params': [] + _PAGINATION_PARAMS,
            },
            'get_instructional_methods': {
                'doc': 'Return the list of instructional methods (online, in-person, hybrid, etc.).',
                'params': [] + _PAGINATION_PARAMS,
            },
            'get_grade_schemes': {
                'doc': 'Return the list of grade schemes (letter, pass/fail, numeric, etc.).',
                'params': [] + _PAGINATION_PARAMS,
            },
            'get_academic_catalogs': {
                'doc': 'Return academic catalogs. Optionally filter by academic year GUID.',
                'params': [
                    {'name': 'academic_year_id', 'type': 'str', 'required': False, 'placeholder': 'Academic year GUID (optional)'},
                ] + _PAGINATION_PARAMS,
            },
            'get_educational_institution': {
                'doc': 'Return a single educational institution record by its Ethos GUID.',
                'params': [
                    {'name': 'institution_id', 'type': 'str', 'required': True, 'placeholder': 'Institution Ethos GUID'},
                ],
            },
            'get_educational_institutions': {
                'doc': 'Search educational institutions. Leave criteria blank to list all.',
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

    from cis.menu import cis_menu, draw_menu
    menu = draw_menu(cis_menu, 'ethos', 'ethos_status')

    return render(request, 'ethos/status.html', {
        'menu': menu,
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

import json as json_mod
import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from cis.models.term import AcademicYear, Term

logger = logging.getLogger(__name__)


def lookup_guid(request):
    """Look up the Ethos GUID for an AcademicYear by calling the academic-periods API.

    Expects GET with ids[] containing a single AcademicYear ID.
    Returns the GUID in a SweetAlert-compatible response.
    """
    ids = request.GET.getlist('ids[]')
    if not ids:
        return JsonResponse({
            'status': 'error',
            'message': 'No academic year selected.',
            'action': 'display',
        })

    record = get_object_or_404(AcademicYear, pk=ids[0])

    from ..library.ethos import Ethos
    ethos = Ethos()

    periods = ethos.get_academic_periods(code=record.code)
    if not periods:
        return JsonResponse({
            'status': 'warning',
            'message': f'No academic period found in Ethos for "{record.code}".',
            'action': 'display',
        })

    guid = periods[0].get('id', '')
    title = periods[0].get('title', record.code)

    return JsonResponse({
        'status': 'success',
        'message': (
            f'{title}<br><br>'
            f'<span id="copy_to_1">{guid}</span>&nbsp;&nbsp;'
            f'<i title="copy to clipboard" class="fas fa fa-paste copy-clipboard" '
            f'data-clipboard-target="#copy_to_1" style="cursor: pointer"></i>'
        ),
        'action': 'display',
        'title': 'Ethos GUID',
    })


def lookup_academic_period(request):
    """AJAX endpoint to look up an academic period by code from Ethos."""
    code = request.GET.get('code', '').strip()
    if not code:
        return JsonResponse({'status': 'error', 'message': 'Code is required.'}, status=400)

    from ..library.ethos import Ethos
    ethos = Ethos()

    periods = ethos.get_academic_periods(code=code)
    if not periods:
        return JsonResponse({'status': 'error', 'message': f'No academic period found for code "{code}".'}, status=404)

    year_period = periods[0]
    descendants = ethos.get_child_academic_periods(year_period['id'], depth=2)

    def build_tree(parent_id, items):
        children = []
        for item in items:
            item_parent = item.get('category', {}).get('parent', {}).get('id')
            if item_parent == parent_id:
                children.append({
                    'period': item,
                    'children': build_tree(item['id'], items)
                })
        return children

    tree = build_tree(year_period['id'], descendants)

    return JsonResponse({
        'status': 'success',
        'year': year_period,
        'children': tree
    })


def create_from_sis(request):
    """AJAX endpoint to create AcademicYear and Terms from Ethos data."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    try:
        data = json_mod.loads(request.body)
    except json_mod.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)

    year_data = data.get('year')
    selected_terms = data.get('terms', [])

    if not year_data or not year_data.get('id'):
        return JsonResponse({'status': 'error', 'message': 'Year data is required.'}, status=400)

    try:
        academic_year = AcademicYear.get_or_add(
            name=year_data.get('title', year_data.get('code')),
            external_sis_id=year_data['id'],
            meta=year_data
        )

        terms_created = 0
        for term_data in selected_terms:
            dates = {}
            if term_data.get('startOn'):
                dates['start'] = term_data['startOn']
            if term_data.get('endOn'):
                dates['end'] = term_data['endOn']

            Term.get_or_add(
                academic_year=academic_year,
                label=term_data.get('title', term_data.get('code')),
                code=term_data.get('code', ''),
                external_sis_id=term_data['id'],
                meta=term_data,
                dates=dates
            )
            terms_created += 1

        return JsonResponse({
            'status': 'success',
            'message': f'Created academic year "{academic_year.name}" with {terms_created} term(s).',
            'academic_year_id': str(academic_year.id),
            'academic_year_name': str(academic_year.name),
        })

    except Exception as e:
        logger.error(f'Error creating from SIS: {e}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

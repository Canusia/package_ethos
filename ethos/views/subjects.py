import json as json_mod
import logging

from django.http import JsonResponse

logger = logging.getLogger(__name__)


def lookup_subjects(request):
    """AJAX endpoint to list subjects from Ethos."""
    from ..library.ethos import Ethos
    ethos = Ethos()

    abbreviation = request.GET.get('abbreviation', '').strip() or None
    subjects = ethos.get_subjects(abbreviation=abbreviation)

    if not subjects:
        return JsonResponse({
            'status': 'warning',
            'message': 'No subjects found in Ethos.',
            'action': 'display',
        })

    return JsonResponse({
        'status': 'success',
        'subjects': subjects,
    })


def create_from_sis(request):
    """AJAX endpoint to create Cohort records from Ethos subjects data."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    try:
        data = json_mod.loads(request.body)
    except json_mod.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)

    selected_subjects = data.get('subjects', [])
    if not selected_subjects:
        return JsonResponse({'status': 'error', 'message': 'No subjects selected.'}, status=400)

    from cis.models.course import Cohort

    try:
        created_count = 0
        for subject_data in selected_subjects:
            abbreviation = subject_data.get('abbreviation', subject_data.get('code', ''))
            title = subject_data.get('title', abbreviation)
            ethos_id = subject_data.get('id', '')

            cohort = Cohort.get_or_add(abbreviation, title)

            if ethos_id and not cohort.external_sis_id:
                cohort.external_sis_id = ethos_id
            cohort.meta = subject_data
            cohort.save()

            created_count += 1

        return JsonResponse({
            'status': 'success',
            'message': f'Synced {created_count} subject(s) from Ethos.',
        })

    except Exception as e:
        logger.error(f'Error creating subjects from SIS: {e}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

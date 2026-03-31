import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from cis.models.course import Course

logger = logging.getLogger(__name__)


def _sync_course(record, ethos):
    """Fetch Ethos data for a single Course and apply updates. Returns (changed_fields, error_message)."""
    course_data = None

    if record.external_sis_id:
        course_data = ethos.get_course_by_id(record.external_sis_id)

    if course_data is None:
        results = ethos.get_courses(number=record.catalog_number)
        subject_abbr = record.cohort.designator if record.cohort else None
        for result in results:
            subject = result.get('subject', {})
            if subject_abbr and subject.get('abbreviation', '').upper() != subject_abbr.upper():
                continue
            course_data = result
            break

    if course_data is None:
        return [], f'No matching course found in Ethos for "{record.name}".'

    changed = []

    ethos_id = course_data.get('id', '')
    if ethos_id and record.external_sis_id != ethos_id:
        record.external_sis_id = ethos_id
        changed.append('Ethos ID')

    title = course_data.get('title', '')
    if title and record.title != title:
        record.title = title
        changed.append('title')

    credits = course_data.get('credits', [])
    if credits:
        credit_hours = credits[0].get('minimum', None)
        if credit_hours is not None and record.credit_hours != credit_hours:
            record.credit_hours = credit_hours
            changed.append('credit hours')

    if record.meta != course_data:
        record.meta = course_data
        changed.append('meta')

    if changed:
        record.save()

    return changed, None


def update_from_ethos(request):
    """Fetch the latest course data from Ethos and update local record(s).

    Expects GET with ids[] containing one or more Course IDs.
    Updates title, credit_hours, meta, and external_sis_id.
    """
    ids = request.GET.getlist('ids[]')
    if not ids:
        return JsonResponse({
            'outcome': 'alert',
            'action': 'display',
            'status': 'error',
            'title': 'Error',
            'message': 'No course selected.',
        })

    from ..library.ethos import Ethos
    ethos = Ethos()

    lines = []
    for course_id in ids:
        record = get_object_or_404(Course, pk=course_id)
        changed, error = _sync_course(record, ethos)
        if error:
            lines.append(f'{record.name}: {error}')
        elif changed:
            lines.append(f'{record.name}: updated {", ".join(changed)}.')
        else:
            lines.append(f'{record.name}: already up to date.')

    return JsonResponse({
        'outcome': 'alert',
        'action': 'display',
        'status': 'success',
        'title': 'Update from Ethos',
        'message': '<br>'.join(lines),
    })

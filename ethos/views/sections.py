import logging

from django.http import JsonResponse

from myce.component_registry.term import term_actions

logger = logging.getLogger(__name__)


@term_actions.action('sis', label='Pull Sections from SIS', icon='fa fa-download', scope=['detail'])
def trigger_section_import(request):
    """POST endpoint to enqueue a section import task for a term."""
    ids = request.POST.getlist('ids[]')
    term_id = ids[0] if ids else request.POST.get('record_id')

    if not term_id:
        return JsonResponse({'outcome': 'alert', 'status': 'error', 'title': 'Error', 'message': 'No term ID provided.'}, status=400)

    from ..tasks import import_sections_for_term
    task_result = import_sections_for_term.enqueue(str(term_id))
    return JsonResponse({
        'outcome': 'alert',
        'status': 'success',
        'title': 'Import Queued',
        'message': f'Section import has been queued. Task ID: {task_result.id}',
    })


def section_import_status(request):
    """GET endpoint to poll the status of a section import task."""
    from django_tasks.backends.database.models import DBTaskResult

    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'status': 'error', 'message': 'No task_id provided.'}, status=400)

    try:
        result = DBTaskResult.objects.get(id=task_id)
    except DBTaskResult.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Task not found.'}, status=404)

    response = {'status': result.status}
    if result.status == 'SUCCEEDED':
        response['counts'] = result.return_value
    elif result.status == 'FAILED':
        response['error'] = str(result.exception_class)
    return JsonResponse(response)

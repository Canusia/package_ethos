import logging

from django.http import JsonResponse

from myce.component_registry.term import term_actions

logger = logging.getLogger(__name__)


def trigger_section_import(request):
    """POST endpoint to enqueue a section import task for a term."""
    ids = request.POST.getlist('ids[]')
    term_id = ids[0] if ids else request.POST.get('record_id')

    if not term_id:
        return JsonResponse({'outcome': 'alert', 'status': 'error', 'title': 'Error', 'message': 'No term ID provided.'}, status=400)

    from ..tasks import import_sections_for_term
    from django.urls import reverse
    task_result = import_sections_for_term.enqueue(str(term_id))
    status_url = request.build_absolute_uri(
        reverse('ethos:ethos_section_import_status') + f'?task_id={task_result.id}'
    )
    return JsonResponse({
        'outcome': 'poll',
        'poll_url': status_url,
        'title': 'Importing Sections',
        'message': 'Section import is running…',
    })


def _registered(registry, slug):
    """Whether ``registry`` already holds an action under ``slug``. Host ActionRegistry
    versions differ per tenant, so read it defensively."""
    find = getattr(registry, '_find_action', None)
    if callable(find):
        return find(slug) is not None
    groups = getattr(registry, '_groups', {}) or {}
    return any(slug in (g.get('actions') or {}) for g in groups.values())


def register_term_action(registry=term_actions):
    """Register 'Pull Sections from SIS' unless the tenant already registered an action
    under the same slug: the tenant's own term import wins (package_ethos#11).

    A tenant that only needs a different fetch/filter should define
    ``SISImporter.fetch_and_import_sections(period_id, term)`` instead; this action's task
    then delegates the whole import to it."""
    if _registered(registry, trigger_section_import.__name__):
        logger.info('ethos: term action %r already registered by the tenant; keeping it.',
                    trigger_section_import.__name__)
        return
    registry.action('sis', label='Pull Sections from SIS', icon='fa fa-download',
                    scope=['detail'])(trigger_section_import)


register_term_action()


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

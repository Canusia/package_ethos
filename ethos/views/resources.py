"""
Ethos Available Resources — list, detail, sync views, and DRF ViewSet.
"""

import logging

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from rest_framework import viewsets

from ..models import EthosApplication, EthosRepresentation, EthosResource
from ..serializers import EthosResourceSerializer
from ..library.ethos import Ethos

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared sync helper (used by view and management command)
# ---------------------------------------------------------------------------

def sync_resources(apps_data):
    """Write API response to DB. Returns (apps_synced, resources_synced)."""
    apps_synced = 0
    resources_synced = 0

    for app in apps_data:
        ethos_id = app.get('id', '')
        if not ethos_id:
            continue

        application, _ = EthosApplication.objects.update_or_create(
            ethos_id=ethos_id,
            defaults={
                'name': app.get('name', ''),
                'about': app.get('about', []),
            },
        )
        apps_synced += 1

        # Replace all resources for this application
        application.resources.all().delete()

        for res in app.get('resources', []):
            # API sometimes returns plain strings instead of resource dicts
            if isinstance(res, str):
                res_name = res
                representations = []
            else:
                res_name = res.get('name', '')
                representations = res.get('representations', [])

            if not res_name:
                continue

            resource = EthosResource.objects.create(
                application=application,
                name=res_name,
            )
            resources_synced += 1

            for rep in representations:
                EthosRepresentation.objects.create(
                    resource=resource,
                    x_media_type=rep.get('X-Media-Type', ''),
                    methods=rep.get('methods', []),
                    version=rep.get('version') or None,
                    filters=rep.get('filters', []),
                    deprecation_notice=rep.get('deprecationNotice') or None,
                )

    return apps_synced, resources_synced


# ---------------------------------------------------------------------------
# DRF ViewSet
# ---------------------------------------------------------------------------

class EthosResourceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EthosResourceSerializer

    def get_queryset(self):
        qs = EthosResource.objects.select_related('application', 'preferred_representation').prefetch_related('representations')
        app = self.request.GET.get('application')
        if app:
            qs = qs.filter(application__id=app)
        return qs.order_by('name')


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def resources_list(request):
    """Render the Ethos resources list page (data loaded via DataTables/DRF)."""

    from cis.menu import cis_menu, draw_menu
    menu = draw_menu(cis_menu, 'ethos', 'ethos_resources')
    
    latest_sync = EthosApplication.objects.order_by('-synced_at').values_list('synced_at', flat=True).first()
    return render(request, 'ethos/resources/index.html', {
        'menu': menu,
        'api_url': '/ce/ethos/api/ethos-resource/?format=datatables',
        'latest_sync': latest_sync,
    })


@require_POST
def resources_sync(request):
    """Trigger a live sync from the Ethos API and redirect back to the list."""
    try:
        ethos = Ethos()
        apps_data = ethos.get_available_resources()
        if not apps_data:
            messages.error(request, 'No data returned from Ethos — check API credentials.')
        else:
            apps_synced, resources_synced = sync_resources(apps_data)
            messages.success(
                request,
                f'Synced {apps_synced} application(s) and {resources_synced} resource(s) from Ethos.',
            )
    except Exception as exc:
        logger.exception('Ethos resource sync failed')
        messages.error(request, f'Sync failed: {exc}')

    return redirect('ethos:ethos_resources')


@require_POST
def resource_set_preferred(request, pk):
    """Save the preferred representation for a resource."""
    resource = get_object_or_404(EthosResource, pk=pk)
    rep_id = request.POST.get('representation_id')
    if rep_id:
        rep = get_object_or_404(EthosRepresentation, pk=rep_id, resource=resource)
        resource.preferred_representation = rep
    else:
        resource.preferred_representation = None
    resource.save(update_fields=['preferred_representation'])

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})

    messages.success(request, f'Preferred representation updated for {resource.name}.')
    return redirect('ethos:ethos_resource_detail', pk=pk)


def resource_detail(request, pk):
    """Detail view for a single Ethos resource showing all representations."""
    resource = get_object_or_404(
        EthosResource.objects.select_related('application').prefetch_related('representations'),
        pk=pk,
    )
    template = (
        'ethos/resources/detail_partial.html'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        else 'ethos/resources/detail.html'
    )
    return render(request, template, {'resource': resource})

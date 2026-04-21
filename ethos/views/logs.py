"""
Ethos API call log — list, detail views and DRF ViewSet.
"""

import json
from urllib.parse import unquote

from django.shortcuts import get_object_or_404, render

from rest_framework import viewsets

from ..models import EthosLog
from ..serializers import EthosLogSerializer


class EthosLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EthosLogSerializer

    def get_queryset(self):
        qs = EthosLog.objects.all()
        message_type = self.request.GET.get('message_type')
        if message_type:
            qs = qs.filter(message_type=message_type)
        return qs


def logs_list(request):

    from cis.menu import cis_menu, draw_menu
    menu = draw_menu(cis_menu, 'ethos', 'ethos_logs')
    
    return render(request, 'ethos/logs/index.html', {
        'menu': menu,
        'api_url': '/ce/ethos/api/ethos-log/?format=datatables',
    })


def _parse_response_body(text):
    """Parse a JSON response body string and re-format it with indentation."""
    if not text:
        return text
    try:
        return json.dumps(json.loads(text), indent=4, ensure_ascii=False)
    except (ValueError, TypeError):
        return text


def log_detail(request, pk):
    log = get_object_or_404(EthosLog, pk=pk)
    template = (
        'ethos/logs/detail_partial.html'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        else 'ethos/logs/detail.html'
    )
    return render(request, template, {
        'log': log,
        'log_url': unquote(log.url or ''),
        'response_body_fmt': _parse_response_body(log.response_body),
    })

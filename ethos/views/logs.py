"""
Ethos API call log — list, detail views and DRF ViewSet.
"""

import json
from urllib.parse import unquote

from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_exempt

from django.utils import timezone

from rest_framework import viewsets
from rest_framework_datatables.filters import DatatablesFilterBackend

from ..campus import for_campus
from ..models import EthosLog
from ..serializers import EthosLogSerializer


def _searched_id(request):
    """The table's global search term as a log id, when it is a plain number."""
    term = (request.query_params.get('search[value]') or '').strip()
    return int(term) if term.isdigit() and len(term) < 19 else None


class EthosLogFilterBackend(DatatablesFilterBackend):
    """The datatables search, plus: a numeric search term also finds the log with that
    id (package_ethos#12). The free-text match on the searchable columns is unchanged."""

    def filter_queryset(self, request, queryset, view):
        filtered = super().filter_queryset(request, queryset, view)
        if request.accepted_renderer.format != 'datatables':
            return filtered
        log_id = _searched_id(request)
        if log_id is None or not queryset.filter(pk=log_id).exists():
            return filtered
        if filtered.filter(pk=log_id).exists():
            return filtered
        # filtered keeps its ordering; the right-hand side brings only the id match.
        combined = filtered | queryset.filter(pk=log_id).distinct()
        view._datatables_filtered_count = getattr(view, '_datatables_filtered_count', 0) + 1
        return combined


class EthosLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EthosLogSerializer
    filter_backends = [EthosLogFilterBackend]

    def get_queryset(self):
        qs = for_campus(EthosLog.objects.all())
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


def _fence(body, lang=''):
    """A markdown code block around ``body``, with a fence longer than any it contains."""
    fence = '```'
    while fence in body:
        fence += '`'
    return f'{fence}{lang}\n{body}\n{fence}'


def _json_block(value):
    """Pretty JSON in a ```json block; raw text in a plain block when it isn't JSON."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return _fence(value)
    return _fence(json.dumps(value, indent=2, ensure_ascii=False), 'json')


def log_copy_text(log):
    """One markdown block describing the call, for pasting into a Claude Code chat
    (package_ethos#12). Full bodies, no truncation. Request headers are the custom ones
    only: EthosLog never stores the Authorization token."""
    sent_on = timezone.localtime(log.sent_on).strftime('%Y-%m-%d %I:%M %p') if log.sent_on else ''
    title = f'Ethos log #{log.pk} — {sent_on}'
    campus = getattr(log, 'campus', None)
    if campus is not None:
        title += f' — campus: {campus.code}'

    lines = [
        title,
        f'{log.method} {unquote(log.url or "")}',
        f'Type: {log.message_type}',
        f'Status: {log.response_status if log.response_status is not None else "(none)"}',
    ]
    if log.description:
        lines.append(f'Description: {log.description}')
    parts = ['\n'.join(lines)]
    if log.request_headers:
        parts.append('Request headers:\n' + _json_block(log.request_headers))
    if log.request_body not in (None, '', {}, []):
        parts.append('Request body:\n' + _json_block(log.request_body))
    else:
        parts.append('Request body: (none)')
    if log.response_body:
        parts.append('Response body:\n' + _json_block(log.response_body))
    else:
        parts.append('Response body: (none)')
    return '\n\n'.join(parts) + '\n'


@xframe_options_exempt
def log_detail(request, pk):
    log = get_object_or_404(for_campus(EthosLog.objects.all()), pk=pk)
    template = (
        'ethos/logs/detail_partial.html'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        else 'ethos/logs/detail.html'
    )
    return render(request, template, {
        'log': log,
        'log_url': unquote(log.url or ''),
        'response_body_fmt': _parse_response_body(log.response_body),
        'copy_text': log_copy_text(log),
    })

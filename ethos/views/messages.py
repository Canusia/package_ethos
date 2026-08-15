"""CE browsing, dry-run, and consume for stored change-notifications."""

import json

from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_exempt

from rest_framework import viewsets
from rest_framework.permissions import BasePermission

from cis.menu import cis_menu, draw_menu

from ..models import EthosMessage
from ..serializers import EthosMessageSerializer
from ..consume.service import consume_message


class HasCERole(BasePermission):
    """Mirrors urls.py's `_has_cis_role` page gate: anonymous denied, 'ce' role
    required. EthosMessage rows can carry a student's name in target_label, so
    the API must be gated the same as the pages that display it — otherwise
    any logged-in student/instructor could list this endpoint directly."""

    def has_permission(self, request, view):
        user = request.user
        if user.is_anonymous:
            return False
        return 'ce' in user.get_roles()


class EthosMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EthosMessageSerializer
    permission_classes = [HasCERole]
    queryset = EthosMessage.objects.all()

    def get_queryset(self):
        # Two optional narrowing filters, driven by query params rather than
        # DataTables' own search: they let the list be linked to directly, e.g.
        # "show me everything that failed" or "just section-registrations",
        # without the operator having to type into the search box.
        qs = EthosMessage.objects.all()
        resource = self.request.GET.get('resource_name')
        if resource:
            qs = qs.filter(resource_name=resource)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


def messages_list(request):
    menu = draw_menu(cis_menu, 'ethos', 'ethos_messages')
    return render(request, 'ethos/messages/index.html', {
        'menu': menu,
        'api_url': '/ce/ethos/api/ethos-message/?format=datatables',
    })


@xframe_options_exempt
def message_detail(request, pk):
    message = get_object_or_404(EthosMessage, pk=pk)
    template = ('ethos/messages/detail_partial.html'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                else 'ethos/messages/detail.html')
    return render(request, template, {
        'message': message,
        'payload_fmt': json.dumps(message.payload, indent=4, ensure_ascii=False),
    })


@xframe_options_exempt
def message_dry_run(request, pk):
    """Render what consuming this message WOULD do. Writes nothing."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    message = get_object_or_404(EthosMessage, pk=pk)
    error = None
    try:
        plan = consume_message(message, dry_run=True)
    except Exception as exc:
        # consume_message() deliberately re-raises plan() failures in dry-run
        # mode. The dry-run panel exists to safely inspect a half-written
        # handler, so a raised exception must render into the panel, not
        # bubble up into a Django 500 page.
        plan = None
        error = str(exc)
    return render(request, 'ethos/messages/_plan.html', {
        'message': message, 'plan': plan, 'dry_run': True, 'error': error,
    })


@xframe_options_exempt
def message_consume(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    message = get_object_or_404(EthosMessage, pk=pk)
    # force=True because a human pressing this button is an explicit
    # instruction: it must work on a message that is already `failed` (the
    # normal re-run after fixing a handler) or `skipped` (a handler was
    # registered after the message arrived), not just on `pending` ones.
    plan = consume_message(message, force=True)
    # The service records the outcome on the row; re-read so the panel renders
    # the status this run just produced rather than the pre-consume one.
    message.refresh_from_db()
    return render(request, 'ethos/messages/_plan.html', {
        'message': message, 'plan': plan, 'dry_run': False,
    })

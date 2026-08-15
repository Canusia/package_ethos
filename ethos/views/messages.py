"""CE browsing, dry-run, and consume for stored change-notifications."""

import json

from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_exempt

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from cis.menu import cis_menu, draw_menu

from ..models import EthosMessage
from ..serializers import EthosMessageSerializer
from ..consume.service import consume_message


class EthosMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EthosMessageSerializer
    permission_classes = [IsAuthenticated]
    queryset = EthosMessage.objects.all()

    def get_queryset(self):
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
    plan = consume_message(message, dry_run=True)
    return render(request, 'ethos/messages/_plan.html', {
        'message': message, 'plan': plan, 'dry_run': True,
    })


@xframe_options_exempt
def message_consume(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    message = get_object_or_404(EthosMessage, pk=pk)
    plan = consume_message(message, force=True)
    message.refresh_from_db()
    return render(request, 'ethos/messages/_plan.html', {
        'message': message, 'plan': plan, 'dry_run': False,
    })

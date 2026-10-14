"""JSON look-up for the Banner Grade Push setting's Look up button."""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from cis.campus_gate import can_manage_settings

from ..grade_push import _log_url
from ..grade_push_config import GradePushConfigError, normalise_guid
from ..grade_push_lookup import BannerLookupError, lookup
from ._client import ethos_client_or_error


@login_required
def grade_push_lookup(request):
    if not can_manage_settings(request.user):
        return JsonResponse({'error': 'You do not have access to settings.'}, status=403)
    try:
        registration = normalise_guid(request.GET.get('registration', ''))
    except ValueError:
        return JsonResponse({'error': 'Enter a section registration GUID.'}, status=400)

    client, error = ethos_client_or_error(request)
    if client is None:
        return JsonResponse({'error': error}, status=400)
    try:
        return JsonResponse(lookup(client, registration))
    except BannerLookupError as exc:
        return JsonResponse({'error': str(exc), 'status': exc.status,
                             'log_url': _log_url(exc.log)}, status=502)
    except GradePushConfigError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

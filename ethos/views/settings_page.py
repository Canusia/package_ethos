"""/ce/ethos/settings/: the sidebar's entry to the Ethos Settings overview.

Menu items are URL names without arguments, so this redirects to the cis
settings overview for the tenant's ``ethos`` profile, or to the Ethos status
page when the tenant has no such profile (or cis predates the overview).
"""
from django.shortcuts import redirect
from django.urls import reverse

try:
    from cis.services.settings_overview import profile_exists
except ImportError:  # cis < 0.1.17a has no settings overview
    def profile_exists(name):
        return False


def ethos_settings(request):
    if profile_exists('ethos'):
        return redirect(reverse('cis:settings_overview', args=['ethos']))
    return redirect(reverse('ethos:ethos_status'))

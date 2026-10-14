"""/ce/ethos/settings/: the sidebar's entry to the Ethos Settings overview.

Menu items are URL names without arguments, so this redirects to the cis
settings overview for the tenant's ``ethos`` profile.
"""
from django.shortcuts import redirect
from django.urls import reverse


def ethos_settings(request):
    return redirect(reverse('cis:settings_overview', args=['ethos']))

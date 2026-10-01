"""Per-campus Ethos credentials (package_ethos#4, ETHOS-01).

Multi-campus deployments read settings.ETHOS_CREDENTIALS[campus.code] (the tenant fills it
from SECRETS['ethos']) and fail closed: a campus never borrows another campus's key or the
deployment key. Single-campus deployments keep using COLLEAGUE_AUTH_CODE.
"""
from django.conf import settings

DEFAULT_URL = 'https://integrate.elluciancloud.com'


class EthosNotConfigured(Exception):
    """The campus has no Ethos credentials."""


def credentials_for(campus):
    from cis.campus_context import is_multi_campus
    if not is_multi_campus():
        return getattr(settings, 'COLLEAGUE_AUTH_CODE', ''), DEFAULT_URL
    code = getattr(campus, 'code', None)
    entry = (getattr(settings, 'ETHOS_CREDENTIALS', None) or {}).get(code) or {}
    if not entry.get('auth_code'):
        raise EthosNotConfigured(f'No Ethos credentials for campus {code}')
    return entry['auth_code'], entry.get('url') or DEFAULT_URL

"""The Ethos client a package command should build payloads with.

A tenant that overrides payload builders (SCCC's ``SCCCEthos``) exposes a no-argument
factory as ``get_client`` in ``<TENANT_SERVICES_APP>.services.ethos_client``. Commands that
preview or validate a payload must use it, so they check exactly what the send path sends.
Without one, the packaged ``Ethos`` is used. Either way the client takes the ambient campus,
which an ``EthosCommand`` sets from ``--campus``.
"""
from django.conf import settings


def get_client():
    factory = None
    if getattr(settings, 'TENANT_SERVICES_APP', None):
        from cis.services.tenant_services import get_tenant_override
        factory = get_tenant_override('ethos_client', 'get_client')
    if factory is not None:
        return factory()
    from .library.ethos import Ethos
    return Ethos()

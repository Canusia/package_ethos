"""Lazy re-export of the tenant-provided SIS importer.

Resolved on attribute access via cis.services.tenant_services so this shared
package never imports a tenant-specific app at module-load time.
"""


def __getattr__(name):
    if name in ('SectionImporter', 'SISImporter'):
        from cis.services.tenant_services import get_tenant_service
        return get_tenant_service('sis_importer').SISImporter
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')

import logging

from django_tasks import task

logger = logging.getLogger(__name__)

# The representation the generic import's ``SISImporter.import_sections`` contract
# parses (instructorRosterDetails, instructionalEvents, ...). Used when no preferred
# 'sections' representation is set, or when the preferred one is not a
# sections-maximum one, so a non-maximum preference cannot change the shape the
# importer is handed (package_ethos#11).
SECTIONS_IMPORT_ACCEPT = 'application/vnd.hedtech.integration.sections-maximum.v16+json'


def sections_import_accept(ethos):
    """The Accept header for the generic term section import.

    A preferred sections-maximum representation (e.g. pinned to v16.2.0 in the
    resource browser) is honoured: it has the shape the importer parses. Any other
    preference, or none, gets ``SECTIONS_IMPORT_ACCEPT``."""
    preferred = ethos.get_preferred_accept_header('sections')
    if isinstance(preferred, str) and 'sections-maximum' in preferred:
        return preferred
    return SECTIONS_IMPORT_ACCEPT

#: Optional tenant hook: ``SISImporter.fetch_and_import_sections(period_id, term) -> dict``.
#: When the tenant's importer defines it, the tenant owns the whole term import
#: (which representation, which sections, what extra context) and the package only
#: resolves the period and the campus (package_ethos#11).
TENANT_IMPORT_HOOK = 'fetch_and_import_sections'


def tenant_import_hook(importer):
    """The tenant importer's bound whole-term import, or None.

    Looked up on the class so only a method the tenant actually defines counts."""
    if callable(getattr(type(importer), TENANT_IMPORT_HOOK, None)):
        return getattr(importer, TENANT_IMPORT_HOOK)
    return None


@task(queue_name='default')
def import_sections_for_term(term_id: str) -> dict:
    """Fetch and import all sections for a term from Ethos. Returns counts dict."""
    from cis.campus_context import campus_context
    from cis.models.term import Term
    from .library.ethos import Ethos
    from cis.services.tenant_services import get_tenant_service
    SectionImporter = get_tenant_service('sis_importer').SISImporter

    term = Term.objects.get(pk=term_id)
    period_id = str(term.external_sis_id) if term.external_sis_id else None

    campus = term.academic_year.campus
    with campus_context(campus):
        if not period_id:
            ethos = Ethos(campus=campus)
            period_id = ethos.get_academic_period_id(term.code)

        if not period_id:
            return {'error': 'Could not resolve Ethos period ID for this term'}

        importer = SectionImporter()
        hook = tenant_import_hook(importer)
        if hook is not None:
            return hook(period_id, term)

        ethos = Ethos(campus=campus)
        raw_sections = ethos.get_sections(period_id=period_id, accept=sections_import_accept(ethos))
        counts = importer.import_sections(raw_sections, term=term)
        counts['total_fetched'] = len(raw_sections)
        return counts

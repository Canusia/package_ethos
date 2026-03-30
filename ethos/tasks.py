import logging

from django_tasks import task

logger = logging.getLogger(__name__)


@task(queue_name='default')
def import_sections_for_term(term_id: str) -> dict:
    """Fetch and import all sections for a term from Ethos. Returns counts dict."""
    from cis.models.term import Term
    from .library.ethos import Ethos
    from cis.services.sis_importer import SISImporter as SectionImporter

    term = Term.objects.get(pk=term_id)
    period_id = str(term.external_sis_id) if term.external_sis_id else None

    if not period_id:
        ethos = Ethos()
        period_id = ethos.get_academic_period_id(term.code)

    if not period_id:
        return {'error': 'Could not resolve Ethos period ID for this term'}

    ethos = Ethos()
    raw_sections = ethos.get_sections(period_id=period_id)
    counts = SectionImporter().import_sections(raw_sections, term=term)
    counts['total_fetched'] = len(raw_sections)
    return counts

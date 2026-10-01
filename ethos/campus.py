"""Campus scoping for Ethos rows (package_ethos#4)."""


def for_campus(qs, path='campus'):
    """Multi-campus: rows of the current campus only. Single-campus: unchanged."""
    from cis.campus_context import current_campus, is_multi_campus
    if not is_multi_campus():
        return qs
    return qs.filter(**{path: current_campus()})

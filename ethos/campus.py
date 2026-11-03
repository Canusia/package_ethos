"""Campus scoping for Ethos rows (package_ethos#4, #14)."""
from django.db.models import Q


def for_campus(qs, path='campus', user=None):
    """Multi-campus: rows of the current campus only. Single-campus: unchanged.

    Pass ``user`` on read-only views: a superuser also sees rows with no campus
    (written before the campus columns, or outside any campus context), which
    no campus would otherwise show (#14). Leave it out where the row is acted
    on (consume, set preferred): those stay on the current campus, because a
    campus-less row could belong to either college. ``assign_ethos_campus``
    gives such rows a campus.
    """
    from cis.campus_context import current_campus, is_multi_campus
    if not is_multi_campus():
        return qs
    condition = Q(**{path: current_campus()})
    if user is not None and getattr(user, 'is_superuser', False):
        condition |= Q(**{f'{path}__isnull': True})
    return qs.filter(condition)


def has_no_campus(obj, attr='campus_id'):
    """True for a multi-campus row with no campus. Always False single-campus."""
    from cis.campus_context import is_multi_campus
    return is_multi_campus() and getattr(obj, attr, None) is None

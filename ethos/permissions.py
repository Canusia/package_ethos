"""DRF permissions shared by the ethos API viewsets."""

from rest_framework.permissions import BasePermission


class HasCERole(BasePermission):
    """Mirrors urls.py's `_has_cis_role` page gate: anonymous denied, 'ce' role
    required. Every ethos API serves data the CE pages show (log URLs carry student
    names and credentials, EthosMessage rows a student's name in target_label), so
    the API must be gated the same as the pages — otherwise any logged-in
    student/instructor could list the endpoint directly."""

    def has_permission(self, request, view):
        user = request.user
        if user.is_anonymous:
            return False
        return 'ce' in user.get_roles()

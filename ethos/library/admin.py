"""
AdminMixin — Ethos admin/management endpoints.
"""

import logging

from .base import EthosBase

logger = logging.getLogger(__name__)


class AdminMixin(EthosBase):
    """Admin operations: available resources, application registry."""

    def get_available_resources(self, **kwargs):
        """Fetch all available Ethos resources/applications.

        Calls GET /admin/available-resources and returns a list of application
        objects. Each object contains:
          - id: application GUID
          - name: application display name
          - about: list of API name/version dicts
          - resources: list of resource objects, each with a ``name`` and
            ``representations`` (supported media types, methods, versions)

        Returns:
            list[dict]: application objects, or empty list on failure.
        """
        url = f'{self.URL}/admin/available-resources'
        resp, sis_log = self._api_request('GET', url, 'available_resources', **kwargs)

        if not resp.ok:
            logger.error(
                'get_available_resources failed: %s %s',
                resp.status_code, resp.text,
            )
            return []

        return resp.json()

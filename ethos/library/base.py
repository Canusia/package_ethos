"""
EthosBase — core infrastructure for Ethos SIS integration.

Provides authentication, API request helpers, GUID loading, and
credential extraction shared by all domain mixins.
"""

import logging, requests, json, time
from django.conf import settings
import jwt

from ..models import EthosLog
from cis.settings.sis_settings import sis_settings

logger = logging.getLogger(__name__)


class EthosBase:
    """Base class with auth, API helpers, and config for Ethos integration."""

    from django.conf import settings

    URL = 'https://integrate.elluciancloud.com'
    AUTH_CODE = getattr(settings, 'COLLEAGUE_AUTH_CODE')

    def __init__(self):
        """Initialize Ethos client with empty token cache."""
        self._cached_token = None
        self._token_expires_at = None

    def get_auth_token(self):
        """Get a cached or fresh JWT token from the Ethos auth endpoint."""
        # Return cached token if still valid (with 30s buffer)
        if (self._cached_token
                and self._token_expires_at
                and time.time() < self._token_expires_at - 30):
            return self._cached_token

        headers = {"Authorization": f"Bearer {self.AUTH_CODE}"}
        url = f'{self.URL}/auth'

        resp = requests.post(url, headers=headers)
        if resp.ok:
            token = resp.text
            payload = jwt.decode(token, options={"verify_signature": False})
            self._token_expires_at = payload.get('exp')
            self._cached_token = token
            return token

        logger.error('Unable to get auth token')
        return None

    def _load_sis_guids(self):
        """Load and parse SIS GUID mappings from database settings."""
        sis_guids = sis_settings.from_db()
        try:
            return json.loads(sis_guids.get('guids', "{}"))
        except Exception as e:
            logger.error('SIS GUIDS Unable to load')
            logger.error(e)
            return {}

    def _api_request(self, method, url, message_type, description='', data=None, json_data=None, headers=None, **kwargs):
        """Make an authenticated API request and log it to EthosLog."""
        token = self.get_auth_token()
        req_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            req_headers.update(headers)

        verbose = kwargs.get('verbose', False)
        if verbose:
            print(url)

        if method == 'GET':
            resp = requests.get(url, headers=req_headers)
        elif method == 'POST':
            resp = requests.post(url, headers=req_headers, data=data, json=json_data)
        elif method == 'PUT':
            resp = requests.put(url, headers=req_headers, data=data, json=json_data)

        if verbose:
            print(resp.status_code, resp.content)

        log = EthosLog.objects.create(
            method=method,
            url=url,
            message_type=message_type,
            description=description,
            request_headers=headers or {},  # custom headers only — Authorization is never stored
            request_body=data or json_data,
            response_status=resp.status_code,
            response_body=resp.text,
        )

        return resp, log

    def _resolve_accept(self, resource_name, override=None, default='application/json'):
        """Return the accept header to use, in priority order:
        explicit override → DB preferred → hardcoded default.
        """
        if override:
            return override
        return self.get_preferred_accept_header(resource_name) or default

    def get_preferred_accept_header(self, resource_name):
        """Return the preferred x_media_type for a resource, or None if not set."""
        from ..models import EthosResource
        try:
            resource = (EthosResource.objects
                        .select_related('preferred_representation')
                        .filter(name=resource_name, preferred_representation__isnull=False)
                        .first())
            if resource:
                return resource.preferred_representation.x_media_type
        except Exception:
            pass
        return None

    def _extract_credential(self, record, cred_type='bannerId'):
        """Extract a credential value from a person record by type."""
        credentials = record.get('credentials')
        if credentials:
            for c in credentials:
                if c.get('type') == cred_type:
                    return c.get('value')
        return None

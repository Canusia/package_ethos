"""
EthosBase — core infrastructure for Ethos SIS integration.

Provides authentication, API request helpers, GUID loading, and
credential extraction shared by all domain mixins.
"""

import logging, requests, json, time
from django.conf import settings
import jwt

from cis.models.sis import SIS_Log
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
        """Make an authenticated API request and log it to SIS_Log."""
        token = self.get_auth_token()
        req_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            req_headers.update(headers)

        sis_log = SIS_Log()
        sis_log.message_type = message_type
        msg = {'url': url, 'data': data or json_data}
        if headers:
            msg['headers'] = headers
        sis_log.message = msg
        if description:
            sis_log.description = description

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

        sis_log.response = {'status': resp.status_code, 'response': resp.text}
        sis_log.save()

        return resp, sis_log

    def _extract_credential(self, record, cred_type='bannerId'):
        """Extract a credential value from a person record by type."""
        credentials = record.get('credentials')
        if credentials:
            for c in credentials:
                if c.get('type') == cred_type:
                    return c.get('value')
        return None

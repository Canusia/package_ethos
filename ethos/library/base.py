"""
EthosBase — core infrastructure for Ethos SIS integration.

Provides authentication, API request helpers, GUID loading, and
credential extraction shared by all domain mixins.
"""

import logging, requests, json, time
from urllib.parse import urlencode
from django.conf import settings
import jwt

from ..models import EthosLog
from cis.settings.sis_settings import sis_settings

logger = logging.getLogger(__name__)


class EthosBase:
    """Base class with auth, API helpers, and config for Ethos integration."""

    from django.conf import settings

    URL = 'https://integrate.elluciancloud.com'
    AUTH_CODE = getattr(settings, 'COLLEAGUE_AUTH_CODE', '')

    #: Seconds before an Ethos call gives up. Without one, a call that never answers
    #: blocks the process indefinitely (package_ethos#3). Override per deployment with
    #: ``settings.ETHOS_REQUEST_TIMEOUT`` or per call with ``timeout=``.
    DEFAULT_TIMEOUT = 30

    @staticmethod
    def request_timeout(timeout=None):
        if timeout is not None:
            return timeout
        from django.conf import settings as django_settings
        return getattr(django_settings, 'ETHOS_REQUEST_TIMEOUT', EthosBase.DEFAULT_TIMEOUT)

    def __init__(self, campus=None):
        """Client for ``campus``. Single-campus deployments are always campus-less
        (``self.campus`` is None -- deployment-wide), ignoring any explicit or ambient
        campus, with no DB query. Multi-campus: explicit campus, else the ambient one
        (request host, CampusCommand, campus_context), else NoCampusContext; a campus
        without credentials raises EthosNotConfigured."""
        from cis.campus_context import current_campus_or_none, is_multi_campus, NoCampusContext
        from ..credentials import credentials_for
        if not is_multi_campus():
            campus = None
        else:
            campus = campus if campus is not None else current_campus_or_none()
            if campus is None:
                raise NoCampusContext('Ethos() needs a campus on a multi-campus deployment.')
        self.campus = campus
        self.AUTH_CODE, self.URL = credentials_for(campus)
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

        resp = requests.post(url, headers=headers, timeout=self.request_timeout())
        if resp.ok:
            token = resp.text
            payload = jwt.decode(token, options={"verify_signature": False})
            self._token_expires_at = payload.get('exp')
            self._cached_token = token
            return token

        logger.error('Unable to get auth token')
        return None

    def _settings_context(self):
        """Campus-scoped settings read by this client must be its own campus's, not the
        ambient one: an Ethos(campus=B) built while serving campus A reads B's rows.
        Campus-less clients (single-campus) read exactly as before."""
        import contextlib
        if self.campus is None:
            return contextlib.nullcontext()
        from cis.campus_context import campus_context
        return campus_context(self.campus)

    @staticmethod
    def _guid_setting(guids, key):
        """The GUID stored under ``key`` in the guids blob, or None.

        Accepts both shapes the blob uses, ``"<guid>"`` and ``{"id": "<guid>"}``. There
        is deliberately no default: a missing key must reach Banner as null (rejected,
        visible), never as a placeholder GUID from another college (package_ethos#3).
        """
        value = guids.get(key)
        if isinstance(value, dict):
            value = value.get('id')
        return value or None

    @staticmethod
    def _phone_digits(value):
        """'+1 (509) 555-1212' -> '5095551212'. Banner expects the bare digits; a US
        country code is dropped so the number is ten digits."""
        import re
        digits = re.sub(r'\D', '', str(value or ''))
        if len(digits) == 11 and digits.startswith('1'):
            return digits[1:]
        return digits

    def _load_sis_guids(self):
        """Load and parse SIS GUID mappings from this client's campus settings."""
        with self._settings_context():
            sis_guids = sis_settings.from_db()
        try:
            return json.loads(sis_guids.get('guids', "{}"))
        except Exception as e:
            logger.error('SIS GUIDS Unable to load')
            logger.error(e)
            return {}

    CONSUME_ACCEPT = 'application/vnd.hedtech.change-notifications.v2+json'

    def get_messages(self, limit=None, last_processed_id=None, **kwargs):
        """Read a batch of change-notifications off this application's queue.

        Returns (records, log). A successful GET ALWAYS advances the queue
        pointer — `last_processed_id` only replays messages still inside Ethos's
        retention window, it does not hold the pointer back. Callers must persist
        a batch before treating it as read.
        """
        params = {}
        if limit is not None:
            params['limit'] = limit
        if last_processed_id is not None:
            params['lastProcessedID'] = last_processed_id

        url = f'{self.URL}/consume'
        if params:
            url = f'{url}?{urlencode(params)}'

        resp, log = self._api_request(
            'GET', url, 'change_notifications',
            headers={'Accept': self.CONSUME_ACCEPT}, **kwargs
        )
        if resp.ok:
            try:
                return resp.json(), log
            except ValueError as e:
                body_prefix = (resp.text or '')[:200]
                logger.error('Unable to parse change-notification batch')
                logger.exception(e)
                raise ValueError(
                    f'Ethos /consume returned 200 with an unparseable body '
                    f'(status={resp.status_code}, body_prefix={body_prefix!r}); '
                    f'the queue pointer has already advanced for this batch, so '
                    f'this cannot be silently treated as an empty queue.'
                ) from e

        logger.error('Unable to read change-notifications: %s', resp.status_code)
        return [], log

    def available_message_count(self, **kwargs):
        """Queue depth via HEAD /consume — the only side-effect-free peek."""
        resp, _log = self._api_request(
            'HEAD', f'{self.URL}/consume', 'change_notifications_peek',
            headers={'Accept': self.CONSUME_ACCEPT}, **kwargs
        )
        if not resp.ok:
            logger.error('Unable to read change-notification queue depth: %s', resp.status_code)
            raise ValueError(
                f'Ethos HEAD /consume returned {resp.status_code}; refusing to '
                f'report a queue depth that may be wrong (e.g. 0) for a failed request.'
            )
        try:
            return int(resp.headers.get('x-remaining', 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _log(self, **fields):
        """Create an EthosLog stamped with this client's campus (None in single-campus mode)."""
        log = EthosLog(campus=self.campus, **fields)
        log.save()
        return log

    def _api_request(self, method, url, message_type, description='', data=None, json_data=None, headers=None, timeout=None, **kwargs):
        """Make an authenticated API request and log it to EthosLog.

        ``timeout`` (seconds) defaults to ``request_timeout()``; a call that runs over
        raises ``requests.Timeout`` rather than hanging.
        """
        timeout = self.request_timeout(timeout)
        token = self.get_auth_token()
        req_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            req_headers.update(headers)

        verbose = kwargs.get('verbose', False)
        if verbose:
            print(url)

        if method == 'GET':
            resp = requests.get(url, headers=req_headers, timeout=timeout)
        elif method == 'POST':
            resp = requests.post(url, headers=req_headers, data=data, json=json_data, timeout=timeout)
        elif method == 'PUT':
            resp = requests.put(url, headers=req_headers, data=data, json=json_data, timeout=timeout)
        elif method == 'HEAD':
            resp = requests.head(url, headers=req_headers, timeout=timeout)
        elif method == 'DELETE':
            resp = requests.delete(url, headers=req_headers, timeout=timeout)
        else:
            raise ValueError(f'Unsupported HTTP method: {method}')

        if verbose:
            print(resp.status_code, resp.content)

        log = self._log(
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
            qs = (EthosResource.objects
                  .select_related('preferred_representation')
                  .filter(name=resource_name, preferred_representation__isnull=False))
            if self.campus is not None:
                qs = qs.filter(application__campus=self.campus)
            resource = qs.first()
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

from __future__ import annotations

import time

import jwt
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Config


class EthosClient:
    """Django-free client for the Ellucian Ethos Integration API."""

    def __init__(self, config: Config):
        self.config = config
        self._token: str | None = None
        self._expires_at: float | None = None
        self._session = requests.Session()
        retry = Retry(
            total=4,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def _auth_token(self) -> str:
        if (
            self._token
            and self._expires_at
            and time.time() < self._expires_at - 30
        ):
            return self._token

        if not self.config.api_key:
            raise RuntimeError(
                "ETHOS_API_KEY is not set — cannot authenticate to Ethos."
            )

        resp = self._session.post(
            self.config.auth_url,
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            timeout=self.config.timeout,
        )
        if resp.status_code in (401, 403):
            raise PermissionError(
                f"Ethos auth rejected ({resp.status_code}) — check ETHOS_API_KEY."
            )
        resp.raise_for_status()

        token = resp.text
        payload = jwt.decode(token, options={"verify_signature": False})
        self._expires_at = payload.get("exp")
        self._token = token
        return token

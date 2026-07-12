from __future__ import annotations

import json
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

    def _headers(self, accept: str | None) -> dict:
        headers = {"Authorization": f"Bearer {self._auth_token()}"}
        if accept:
            headers["Accept"] = accept
        return headers

    @staticmethod
    def _check(resp) -> None:
        if resp.status_code in (401, 403):
            raise PermissionError(
                f"Ethos denied the request ({resp.status_code}). "
                "Check the API key's rights."
            )
        resp.raise_for_status()

    def get_entity(self, path: str, key: str, accept: str | None = None):
        url = f"{self.config.base_url}/{path.strip('/')}/{key}"
        resp = self._session.get(
            url, headers=self._headers(accept), timeout=self.config.timeout
        )
        if resp.status_code == 404:
            return None
        self._check(resp)
        return resp.json()

    def get_collection(
        self,
        path: str,
        *,
        criteria: dict | None = None,
        accept: str | None = None,
        extra_params: dict | None = None,
    ) -> list:
        base_params: dict = {}
        if criteria:
            base_params["criteria"] = json.dumps(criteria)
        if extra_params:
            base_params.update(extra_params)

        url = f"{self.config.base_url}/{path.strip('/')}"
        results: list = []
        offset = 0
        while True:
            params = dict(base_params, offset=offset)
            resp = self._session.get(
                url,
                headers=self._headers(accept),
                params=params,
                timeout=self.config.timeout,
            )
            self._check(resp)
            page = resp.json()
            if not isinstance(page, list):
                page = [page]
            results.extend(page)

            total = resp.headers.get("x-total-count")
            page_size = int(resp.headers.get("x-max-page-size", 500))
            if total is not None and len(results) >= int(total):
                break
            if len(page) < page_size:
                break
            if not page:
                break
            offset += len(page)
        return results

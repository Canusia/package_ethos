from __future__ import annotations

import json
import os
from dataclasses import dataclass


def _load_dotenv() -> None:
    """Load a .env file if python-dotenv is installed; silently skip otherwise."""
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv()


@dataclass(frozen=True)
class Config:
    base_url: str
    api_key: str
    timeout: float
    guids: dict

    @property
    def auth_url(self) -> str:
        return f"{self.base_url}/auth"


def load_config() -> Config:
    _load_dotenv()
    base_url = os.environ.get(
        "ETHOS_BASE_URL", "https://integrate.elluciancloud.com"
    ).rstrip("/")
    api_key = os.environ.get("ETHOS_API_KEY", "")
    timeout = float(os.environ.get("ETHOS_TIMEOUT", "30"))
    guids_raw = os.environ.get("ETHOS_GUIDS_JSON", "")
    guids = json.loads(guids_raw) if guids_raw else {}
    return Config(base_url=base_url, api_key=api_key, timeout=timeout, guids=guids)

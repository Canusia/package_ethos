import json
import os
import unittest
from unittest import mock

from ethos_sis.config import Config, load_config


class ConfigTest(unittest.TestCase):
    def test_auth_url_appends_auth_path(self):
        cfg = Config(base_url="https://example.test", api_key="k", timeout=30.0, guids={})
        self.assertEqual(cfg.auth_url, "https://example.test/auth")

    @mock.patch.dict(os.environ, {}, clear=True)
    @mock.patch("ethos_sis.config._load_dotenv")  # ignore any real .env beside the repo
    def test_defaults_when_env_absent(self, _dotenv):
        cfg = load_config()
        self.assertEqual(cfg.base_url, "https://integrate.elluciancloud.com")
        self.assertEqual(cfg.api_key, "")
        self.assertEqual(cfg.timeout, 30.0)
        self.assertEqual(cfg.guids, {})

    @mock.patch.dict(
        os.environ,
        {
            "ETHOS_BASE_URL": "https://sandbox.test/",
            "ETHOS_API_KEY": "secret-key",
            "ETHOS_TIMEOUT": "12.5",
            "ETHOS_GUIDS_JSON": json.dumps({"ethnicities": {"H": "guid-1"}}),
        },
        clear=True,
    )
    def test_reads_env_and_strips_trailing_slash(self):
        cfg = load_config()
        self.assertEqual(cfg.base_url, "https://sandbox.test")  # trailing slash stripped
        self.assertEqual(cfg.api_key, "secret-key")
        self.assertEqual(cfg.timeout, 12.5)
        self.assertEqual(cfg.guids, {"ethnicities": {"H": "guid-1"}})

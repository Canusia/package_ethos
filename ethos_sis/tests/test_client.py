import time
import unittest
from unittest import mock

from ethos_sis.client import EthosClient
from ethos_sis.config import Config


def make_client(api_key="key"):
    cfg = Config(base_url="https://ethos.test", api_key=api_key, timeout=30.0, guids={})
    return EthosClient(cfg)


def fake_response(status=200, *, text="", json_data=None, headers=None):
    resp = mock.MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 300
    resp.text = text
    resp.headers = headers or {}
    resp.json.return_value = json_data
    return resp


class AuthTokenTest(unittest.TestCase):
    def test_missing_api_key_raises(self):
        client = make_client(api_key="")
        with self.assertRaises(RuntimeError):
            client._auth_token()

    def test_mints_and_caches(self):
        client = make_client()
        future = int(time.time()) + 3600
        with mock.patch.object(client._session, "post",
                               return_value=fake_response(text="jwt-token-abc")) as post, \
             mock.patch("ethos_sis.client.jwt.decode", return_value={"exp": future}):
            t1 = client._auth_token()
            t2 = client._auth_token()  # second call must reuse cache, not re-POST
        self.assertEqual(t1, "jwt-token-abc")
        self.assertEqual(t2, "jwt-token-abc")
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://ethos.test/auth")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer key")

    def test_401_raises_permission_error(self):
        client = make_client()
        with mock.patch.object(client._session, "post",
                               return_value=fake_response(status=401, text="nope")):
            with self.assertRaises(PermissionError):
                client._auth_token()

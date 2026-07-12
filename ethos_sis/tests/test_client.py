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


class GetEntityTest(unittest.TestCase):
    def test_returns_json(self):
        client = make_client()
        with mock.patch.object(client, "_auth_token", return_value="t"), \
             mock.patch.object(client._session, "get",
                               return_value=fake_response(json_data={"id": "abc"})) as get:
            result = client.get_entity("api/subjects", "abc", accept="application/json")
        self.assertEqual(result, {"id": "abc"})
        args, kwargs = get.call_args
        self.assertEqual(args[0], "https://ethos.test/api/subjects/abc")
        self.assertEqual(kwargs["headers"]["Accept"], "application/json")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer t")

    def test_404_returns_none(self):
        client = make_client()
        with mock.patch.object(client, "_auth_token", return_value="t"), \
             mock.patch.object(client._session, "get",
                               return_value=fake_response(status=404, text="")):
            self.assertIsNone(client.get_entity("api/subjects", "missing"))


class GetCollectionTest(unittest.TestCase):
    def test_single_page(self):
        client = make_client()
        page = [{"id": "1"}, {"id": "2"}]
        resp = fake_response(json_data=page, headers={"x-total-count": "2",
                                                       "x-max-page-size": "500"})
        with mock.patch.object(client, "_auth_token", return_value="t"), \
             mock.patch.object(client._session, "get", return_value=resp) as get:
            rows = client.get_collection("api/subjects",
                                         criteria={"abbreviation": "MATH"},
                                         accept="application/json")
        self.assertEqual(rows, page)
        get.assert_called_once()
        _, kwargs = get.call_args
        self.assertEqual(kwargs["params"]["criteria"], '{"abbreviation": "MATH"}')
        self.assertEqual(kwargs["params"]["offset"], 0)

    def test_follows_offset_pages_until_total_count(self):
        client = make_client()
        page1 = [{"id": str(i)} for i in range(3)]
        page2 = [{"id": "3"}]
        resp1 = fake_response(json_data=page1, headers={"x-total-count": "4",
                                                        "x-max-page-size": "3"})
        resp2 = fake_response(json_data=page2, headers={"x-total-count": "4",
                                                        "x-max-page-size": "3"})
        with mock.patch.object(client, "_auth_token", return_value="t"), \
             mock.patch.object(client._session, "get", side_effect=[resp1, resp2]) as get:
            rows = client.get_collection("api/subjects")
        self.assertEqual([r["id"] for r in rows], ["0", "1", "2", "3"])
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[1].kwargs["params"]["offset"], 3)

    def test_403_raises_permission_error(self):
        client = make_client()
        with mock.patch.object(client, "_auth_token", return_value="t"), \
             mock.patch.object(client._session, "get",
                               return_value=fake_response(status=403, text="denied")):
            with self.assertRaises(PermissionError):
                client.get_collection("api/subjects")

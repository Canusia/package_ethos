import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import admin
from ethos_sis.tests._fakes import FakeClient, ns


class AdminTest(unittest.TestCase):
    def test_resources_hits_admin_path(self):
        client = FakeClient(collection=[{"name": "app1"}])
        with redirect_stdout(io.StringIO()):
            admin.cmd_resources(client, ns())
        self.assertEqual(client.calls[0][1], "admin/available-resources")

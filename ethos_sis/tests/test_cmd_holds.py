import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import holds
from ethos_sis.tests._fakes import FakeClient, ns


class HoldsTest(unittest.TestCase):
    def test_list_criteria_and_v6(self):
        client = FakeClient(collection=[{"id": "h1"}])
        with redirect_stdout(io.StringIO()):
            holds.cmd_list(client, ns(person_id="p1"))
        self.assertEqual(client.calls[0][2], {"person": {"id": "p1"}})
        self.assertIn("v6", client.calls[0][3])

    def test_get_entity_v6(self):
        client = FakeClient(entity={"id": "h1"})
        with redirect_stdout(io.StringIO()):
            holds.cmd_get(client, ns(id="h1"))
        self.assertEqual(client.calls[0][:3], ("entity", "api/person-holds", "h1"))
        self.assertIn("v6", client.calls[0][3])

    def test_type_codes_no_criteria(self):
        client = FakeClient(collection=[{"id": "tc"}])
        with redirect_stdout(io.StringIO()):
            holds.cmd_type_codes(client, ns())
        self.assertIsNone(client.calls[0][2])

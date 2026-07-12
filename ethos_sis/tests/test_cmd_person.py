import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import person
from ethos_sis.tests._fakes import FakeClient, ns

PERSON = {"id": "p1", "credentials": [{"type": "bannerId", "value": "B123"}]}


class PersonTest(unittest.TestCase):
    def test_get_entity(self):
        client = FakeClient(entity=PERSON)
        with redirect_stdout(io.StringIO()):
            person.cmd_get(client, ns(id="p1"))
        self.assertEqual(client.calls[0][:3], ("entity", "api/persons", "p1"))

    def test_lookup_banner_id_criteria(self):
        client = FakeClient(collection=[PERSON])
        with redirect_stdout(io.StringIO()):
            person.cmd_lookup(client, ns(banner_id="B123", colleague_id=None,
                                         alt_cred=None, alt_type_id=None))
        self.assertEqual(
            client.calls[0][2],
            {"credentials": [{"type": "bannerId", "value": "B123"}]},
        )

    def test_lookup_colleague_id_criteria(self):
        client = FakeClient(collection=[PERSON])
        with redirect_stdout(io.StringIO()):
            person.cmd_lookup(client, ns(banner_id=None, colleague_id="C9",
                                         alt_cred=None, alt_type_id=None))
        self.assertEqual(
            client.calls[0][2],
            {"credentials": [{"type": "colleaguePersonId", "value": "C9"}]},
        )

    def test_lookup_alt_cred_criteria(self):
        client = FakeClient(collection=[PERSON])
        with redirect_stdout(io.StringIO()):
            person.cmd_lookup(client, ns(banner_id=None, colleague_id=None,
                                         alt_cred="A1", alt_type_id="t1"))
        self.assertEqual(
            client.calls[0][2],
            {"alternativeCredentials": [{"type": {"id": "t1"}, "value": "A1"}]},
        )

    def test_lookup_requires_a_selector(self):
        client = FakeClient()
        with self.assertRaises(ValueError):
            person.cmd_lookup(client, ns(banner_id=None, colleague_id=None,
                                         alt_cred=None, alt_type_id=None))

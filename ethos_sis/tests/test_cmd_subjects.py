import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import subjects
from ethos_sis.tests._fakes import FakeClient, ns

SUBJECT = {"id": "guid-1", "abbreviation": "MATH", "title": "Mathematics"}


class SubjectsListTest(unittest.TestCase):
    def test_list_calls_collection_and_prints(self):
        client = FakeClient(collection=[SUBJECT])
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = subjects.cmd_list(client, ns(abbreviation=None))
        self.assertEqual(rc, 0)
        self.assertEqual(client.calls[0][0], "collection")
        self.assertEqual(client.calls[0][1], "api/subjects")
        self.assertIn("MATH", buf.getvalue())

    def test_list_builds_abbreviation_criteria(self):
        client = FakeClient(collection=[SUBJECT])
        with redirect_stdout(io.StringIO()):
            subjects.cmd_list(client, ns(abbreviation="MATH"))
        self.assertEqual(client.calls[0][2], {"abbreviation": "MATH"})


class SubjectsGetTest(unittest.TestCase):
    def test_get_calls_entity(self):
        client = FakeClient(entity=SUBJECT)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = subjects.cmd_get(client, ns(id="guid-1"))
        self.assertEqual(rc, 0)
        self.assertEqual(client.calls[0], ("entity", "api/subjects", "guid-1",
                                           "application/json"))
        self.assertIn("Mathematics", buf.getvalue())

    def test_get_missing_prints_not_found(self):
        client = FakeClient(entity=None)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = subjects.cmd_get(client, ns(id="nope"))
        self.assertEqual(rc, 0)
        self.assertIn("Not found", buf.getvalue())

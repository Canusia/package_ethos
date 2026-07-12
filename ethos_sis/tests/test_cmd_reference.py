import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import reference as ref
from ethos_sis.tests._fakes import FakeClient, ns


class ReferenceTest(unittest.TestCase):
    def test_academic_levels_no_criteria(self):
        client = FakeClient(collection=[{"id": "l1"}])
        with redirect_stdout(io.StringIO()):
            ref.cmd_academic_levels(client, ns())
        self.assertEqual(client.calls[0][1], "api/academic-levels")
        self.assertIsNone(client.calls[0][2])

    def test_catalogs_with_year(self):
        client = FakeClient(collection=[{"id": "c1"}])
        with redirect_stdout(io.StringIO()):
            ref.cmd_academic_catalogs(client, ns(year_id="y1"))
        self.assertEqual(client.calls[0][2], {"academicYear": {"id": "y1"}})

    def test_institution_entity(self):
        client = FakeClient(entity={"id": "i1"})
        with redirect_stdout(io.StringIO()):
            ref.cmd_institution(client, ns(id="i1"))
        self.assertEqual(client.calls[0][:3],
                         ("entity", "api/educational-institutions", "i1"))

    def test_institutions_parses_criteria_json(self):
        client = FakeClient(collection=[{"id": "i1"}])
        with redirect_stdout(io.StringIO()):
            ref.cmd_institutions(client, ns(criteria='{"type": "postSecondary"}'))
        self.assertEqual(client.calls[0][2], {"type": "postSecondary"})

    def test_institutions_bad_json_raises(self):
        client = FakeClient(collection=[])
        with self.assertRaises(ValueError):
            ref.cmd_institutions(client, ns(criteria="{not json"))

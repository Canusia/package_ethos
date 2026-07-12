import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import sections
from ethos_sis.tests._fakes import FakeClient, ns

SECTION = {"id": "s1", "number": "01", "titles": [{"value": "Bio 101"}]}


class SectionsListTest(unittest.TestCase):
    def test_period_id_builds_detail_criteria(self):
        client = FakeClient(collection=[SECTION])
        with redirect_stdout(io.StringIO()):
            sections.cmd_list(client, ns(term_code=None, period_id="p1", accept=None))
        # single call: no period resolution needed
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][1], "api/sections")
        self.assertEqual(client.calls[0][2],
                         {"academicPeriod": {"detail": {"id": "p1"}}})
        self.assertIn("sections-maximum", client.calls[0][3])

    def test_term_code_resolves_period_first(self):
        # First get_collection resolves the term code -> period; second lists sections.
        client = FakeClient(collection=[{"id": "p9", "code": "24/FA"}])
        with redirect_stdout(io.StringIO()):
            sections.cmd_list(client, ns(term_code="24/FA", period_id=None, accept=None))
        self.assertEqual(client.calls[0][1], "api/academic-periods")
        self.assertEqual(client.calls[1][1], "api/sections")
        self.assertEqual(client.calls[1][2],
                         {"academicPeriod": {"detail": {"id": "p9"}}})

    def test_requires_a_period_source(self):
        client = FakeClient()
        with self.assertRaises(ValueError):
            sections.cmd_list(client, ns(term_code=None, period_id=None, accept=None))


class SectionsGetTest(unittest.TestCase):
    def test_get_entity(self):
        client = FakeClient(entity=SECTION)
        buf = io.StringIO()
        with redirect_stdout(buf):
            sections.cmd_get(client, ns(id="s1", accept=None))
        self.assertEqual(client.calls[0][:3], ("entity", "api/sections", "s1"))

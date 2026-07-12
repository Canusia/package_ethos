import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import academic_periods as ap
from ethos_sis.tests._fakes import FakeClient, ns

GUID = "12345678-1234-1234-1234-123456789012"
YEAR = {"id": GUID, "code": "2024", "title": "2024-2025",
        "category": {"type": "year"}}
TERM = {"id": "term-1", "code": "24/FA", "title": "Fall",
        "category": {"type": "term", "parent": {"id": GUID}}}


class ListTest(unittest.TestCase):
    def test_code_and_category_criteria(self):
        client = FakeClient(collection=[YEAR])
        with redirect_stdout(io.StringIO()):
            ap.cmd_list(client, ns(code="2024", category="year"))
        self.assertEqual(client.calls[0][2],
                         {"code": "2024", "category": {"type": "year"}})


class ResolveTest(unittest.TestCase):
    def test_is_guid(self):
        self.assertTrue(ap._is_guid(GUID))
        self.assertFalse(ap._is_guid("24/FA"))

    def test_get_by_guid_uses_entity(self):
        client = FakeClient(entity=YEAR)
        buf = io.StringIO()
        with redirect_stdout(buf):
            ap.cmd_get(client, ns(id=GUID))
        self.assertEqual(client.calls[0][0], "entity")
        self.assertIn("2024-2025", buf.getvalue())

    def test_get_by_code_uses_collection(self):
        client = FakeClient(collection=[YEAR])
        with redirect_stdout(io.StringIO()):
            ap.cmd_get(client, ns(id="2024"))
        self.assertEqual(client.calls[0][0], "collection")
        self.assertEqual(client.calls[0][2], {"code": "2024"})


class ChildrenTest(unittest.TestCase):
    def test_filters_by_parent_id(self):
        # First call resolves parent (by GUID -> entity); second lists all.
        client = FakeClient(collection=[YEAR, TERM], entity=YEAR)
        buf = io.StringIO()
        with redirect_stdout(buf):
            ap.cmd_children(client, ns(parent=GUID))
        out = buf.getvalue()
        self.assertIn("24/FA", out)     # TERM is a child of YEAR
        self.assertNotIn("2024-2025", out)  # YEAR itself excluded

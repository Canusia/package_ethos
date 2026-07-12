import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import courses
from ethos_sis.tests._fakes import FakeClient, ns

COURSE = {"id": "c1", "number": "101", "title": "Intro"}


class CoursesTest(unittest.TestCase):
    def test_list_builds_criteria(self):
        client = FakeClient(collection=[COURSE])
        with redirect_stdout(io.StringIO()):
            courses.cmd_list(client, ns(number="101", title=None))
        self.assertEqual(client.calls[0][1], "api/courses")
        self.assertEqual(client.calls[0][2], {"number": "101"})

    def test_list_no_filters_sends_none(self):
        client = FakeClient(collection=[COURSE])
        with redirect_stdout(io.StringIO()):
            courses.cmd_list(client, ns(number=None, title=None))
        self.assertIsNone(client.calls[0][2])

    def test_get_calls_entity(self):
        client = FakeClient(entity=COURSE)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = courses.cmd_get(client, ns(id="c1"))
        self.assertEqual(rc, 0)
        self.assertEqual(client.calls[0][:3], ("entity", "api/courses", "c1"))
        self.assertIn("Intro", buf.getvalue())

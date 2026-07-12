import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import student_records as sr
from ethos_sis.tests._fakes import FakeClient, ns


class StudentRecordsTest(unittest.TestCase):
    def test_get_entity(self):
        client = FakeClient(entity={"id": "p1"})
        with redirect_stdout(io.StringIO()):
            sr.cmd_get(client, ns(person_id="p1"))
        self.assertEqual(client.calls[0][:3], ("entity", "api/students", "p1"))

    def test_programs_uses_v17(self):
        client = FakeClient(collection=[{"id": "x"}])
        with redirect_stdout(io.StringIO()):
            sr.cmd_programs(client, ns(person_id="p1"))
        self.assertIn("v17", client.calls[0][3])
        self.assertEqual(client.calls[0][2], {"student": {"id": "p1"}})

    def test_course_registrations_registrant_and_period(self):
        client = FakeClient(collection=[{"id": "x"}])
        with redirect_stdout(io.StringIO()):
            sr.cmd_course_registrations(client, ns(person_id="p1", period_id="t1"))
        self.assertEqual(
            client.calls[0][2],
            {"registrant": {"id": "p1"}, "academicPeriod": {"id": "t1"}},
        )

    def test_course_registrations_without_period(self):
        client = FakeClient(collection=[{"id": "x"}])
        with redirect_stdout(io.StringIO()):
            sr.cmd_course_registrations(client, ns(person_id="p1", period_id=None))
        self.assertEqual(client.calls[0][2], {"registrant": {"id": "p1"}})

    def test_types_no_criteria(self):
        client = FakeClient(collection=[{"id": "x"}])
        with redirect_stdout(io.StringIO()):
            sr.cmd_types(client, ns())
        self.assertIsNone(client.calls[0][2])

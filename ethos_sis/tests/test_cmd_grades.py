import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import grades
from ethos_sis.tests._fakes import FakeClient, ns


class GradesTest(unittest.TestCase):
    def test_student_grades_with_period(self):
        client = FakeClient(collection=[{"id": "g1"}])
        with redirect_stdout(io.StringIO()):
            grades.cmd_student_grades(client, ns(person_id="p1", period_id="t1"))
        self.assertEqual(
            client.calls[0][2],
            {"student": {"id": "p1"}, "academicPeriod": {"id": "t1"}},
        )

    def test_definitions_with_scheme(self):
        client = FakeClient(collection=[{"id": "d1"}])
        with redirect_stdout(io.StringIO()):
            grades.cmd_definitions(client, ns(scheme_id="s1"))
        self.assertEqual(client.calls[0][2], {"scheme": {"id": "s1"}})

    def test_definitions_without_scheme(self):
        client = FakeClient(collection=[{"id": "d1"}])
        with redirect_stdout(io.StringIO()):
            grades.cmd_definitions(client, ns(scheme_id=None))
        self.assertIsNone(client.calls[0][2])

    def test_gpa_criteria(self):
        client = FakeClient(collection=[{"id": "gpa"}])
        with redirect_stdout(io.StringIO()):
            grades.cmd_gpa(client, ns(person_id="p1"))
        self.assertEqual(client.calls[0][1], "api/student-grade-point-averages")
        self.assertEqual(client.calls[0][2], {"student": {"id": "p1"}})

    def test_section_grade_types_criteria(self):
        client = FakeClient(collection=[{"id": "sgt"}])
        with redirect_stdout(io.StringIO()):
            grades.cmd_section_grade_types(client, ns(section_id="sec1"))
        self.assertEqual(client.calls[0][2], {"section": {"id": "sec1"}})

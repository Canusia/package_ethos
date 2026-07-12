import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import registration
from ethos_sis.tests._fakes import FakeClient, ns


class RegistrationTest(unittest.TestCase):
    def test_eligibility_criteria(self):
        client = FakeClient(collection=[{"eligibilityStatus": "eligible"}])
        with redirect_stdout(io.StringIO()):
            registration.cmd_eligibility(client, ns(student_id="p1", period_id="t1"))
        self.assertEqual(client.calls[0][1], "api/student-registration-eligibilities")
        self.assertEqual(
            client.calls[0][2],
            {"student": {"id": "p1"}, "academicPeriod": {"id": "t1"}},
        )

    def test_eligibility_empty(self):
        client = FakeClient(collection=[])
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = registration.cmd_eligibility(client, ns(student_id="p1", period_id="t1"))
        self.assertEqual(rc, 0)
        self.assertIn("No", buf.getvalue())

import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import student_account as sa
from ethos_sis.tests._fakes import FakeClient, ns


class StudentAccountTest(unittest.TestCase):
    def test_summary_criteria(self):
        client = FakeClient(collection=[{"id": "sum1"}])
        with redirect_stdout(io.StringIO()):
            sa.cmd_summary(client, ns(person_id="p1"))
        self.assertEqual(client.calls[0][1], "api/student-account-summaries")
        self.assertEqual(client.calls[0][2], {"student": {"id": "p1"}})

    def test_details_with_period(self):
        client = FakeClient(collection=[{"id": "d1"}])
        with redirect_stdout(io.StringIO()):
            sa.cmd_details(client, ns(person_id="p1", period_id="t1"))
        self.assertEqual(
            client.calls[0][2],
            {"student": {"id": "p1"}, "academicPeriod": {"id": "t1"}},
        )

    def test_aid_awards_with_year(self):
        client = FakeClient(collection=[{"id": "a1"}])
        with redirect_stdout(io.StringIO()):
            sa.cmd_financial_aid_awards(client, ns(person_id="p1", aid_year_id="y1"))
        self.assertEqual(
            client.calls[0][2],
            {"student": {"id": "p1"}, "aidYear": {"id": "y1"}},
        )

    def test_aid_years_no_criteria(self):
        client = FakeClient(collection=[{"id": "y1"}])
        with redirect_stdout(io.StringIO()):
            sa.cmd_financial_aid_years(client, ns())
        self.assertIsNone(client.calls[0][2])

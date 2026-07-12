import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import academic
from ethos_sis.tests._fakes import FakeClient, ns


class AcademicTest(unittest.TestCase):
    def test_programs_with_code(self):
        client = FakeClient(collection=[{"id": "pr1"}])
        with redirect_stdout(io.StringIO()):
            academic.cmd_programs(client, ns(code="BIO"))
        self.assertEqual(client.calls[0][1], "api/academic-programs")
        self.assertEqual(client.calls[0][2], {"code": "BIO"})

    def test_programs_without_code(self):
        client = FakeClient(collection=[{"id": "pr1"}])
        with redirect_stdout(io.StringIO()):
            academic.cmd_programs(client, ns(code=None))
        self.assertIsNone(client.calls[0][2])

    def test_sites_no_criteria(self):
        client = FakeClient(collection=[{"id": "s1"}])
        with redirect_stdout(io.StringIO()):
            academic.cmd_sites(client, ns())
        self.assertEqual(client.calls[0][1], "api/sites")
        self.assertIsNone(client.calls[0][2])

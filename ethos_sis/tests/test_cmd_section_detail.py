import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import section_detail as sd
from ethos_sis.tests._fakes import FakeClient, ns


class SectionDetailTest(unittest.TestCase):
    def test_meeting_times_criteria(self):
        client = FakeClient(collection=[{"id": "m1"}])
        with redirect_stdout(io.StringIO()):
            sd.cmd_meeting_times(client, ns(section_id="s1"))
        self.assertEqual(client.calls[0][1], "api/section-meeting-times")
        self.assertEqual(client.calls[0][2], {"section": {"id": "s1"}})

    def test_registrations_uses_v16_accept(self):
        client = FakeClient(collection=[{"id": "r1"}])
        with redirect_stdout(io.StringIO()):
            sd.cmd_registrations(client, ns(section_id="s1"))
        self.assertIn("v16", client.calls[0][3])

    def test_enrollment_is_entity_call(self):
        client = FakeClient(entity={"id": "e1"})
        with redirect_stdout(io.StringIO()):
            sd.cmd_enrollment(client, ns(section_id="s1"))
        self.assertEqual(client.calls[0][:3],
                         ("entity", "api/section-enrollment-information", "s1"))

    def test_registration_statuses_no_criteria(self):
        client = FakeClient(collection=[{"id": "st1"}])
        with redirect_stdout(io.StringIO()):
            sd.cmd_registration_statuses(client, ns())
        self.assertIsNone(client.calls[0][2])

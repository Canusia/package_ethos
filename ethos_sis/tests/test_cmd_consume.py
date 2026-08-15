import io
import unittest
from contextlib import redirect_stdout

from ethos_sis.commands import consume
from ethos_sis.tests._fakes import FakeClient, ns


NOTIFICATION = {
    "id": "42",
    "published": "2026-08-15T12:00:00Z",
    "operation": "replaced",
    "resource": {"name": "sections", "id": "abc", "version": "v16"},
    "publisher": {"id": "pub-1"},
    "contentType": "application/vnd.hedtech.integration.v16+json",
    "content": {"id": "abc"},
}


class ConsumeTest(unittest.TestCase):
    def test_passes_limit_and_last_processed_id(self):
        client = FakeClient(messages=[NOTIFICATION], remaining=7)
        with redirect_stdout(io.StringIO()):
            consume.cmd_consume(client, ns(limit=5, last_processed_id=41, peek=False))
        self.assertEqual(client.calls[0], ("consume", 5, 41))

    def test_reports_remaining_count(self):
        client = FakeClient(messages=[NOTIFICATION], remaining=7)
        buf = io.StringIO()
        with redirect_stdout(buf):
            consume.cmd_consume(client, ns(limit=None, last_processed_id=None, peek=False))
        self.assertIn("7 message(s) remaining", buf.getvalue())

    def test_empty_queue_says_so(self):
        client = FakeClient(messages=[], remaining=0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            consume.cmd_consume(client, ns(limit=None, last_processed_id=None, peek=False))
        self.assertIn("No results.", buf.getvalue())

    def test_peek_does_not_drain(self):
        client = FakeClient(messages=[NOTIFICATION], remaining=3)
        buf = io.StringIO()
        with redirect_stdout(buf):
            consume.cmd_consume(client, ns(limit=None, last_processed_id=None, peek=True))
        self.assertEqual(client.calls, [("peek",)])
        self.assertIn("3 message(s)", buf.getvalue())

    def test_json_output_is_raw_notifications(self):
        client = FakeClient(messages=[NOTIFICATION], remaining=0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            consume.cmd_consume(client, ns(limit=None, last_processed_id=None,
                                           peek=False, json=True))
        self.assertIn('"contentType"', buf.getvalue())

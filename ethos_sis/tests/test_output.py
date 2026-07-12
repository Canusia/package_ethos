import argparse
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from ethos_sis.output import dotted_get, emit


def ns(**kw):
    kw.setdefault("json", False)
    kw.setdefault("out", None)
    return argparse.Namespace(**kw)


class DottedGetTest(unittest.TestCase):
    def test_resolves_nested(self):
        self.assertEqual(dotted_get({"a": {"b": {"c": 5}}}, "a.b.c"), 5)

    def test_missing_returns_empty(self):
        self.assertEqual(dotted_get({"a": {}}, "a.b.c"), "")


class EmitTest(unittest.TestCase):
    def test_json_mode(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            emit([{"id": "1"}], ns(json=True))
        self.assertEqual(json.loads(buf.getvalue()), [{"id": "1"}])

    def test_table_mode_uses_columns(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            emit([{"id": "1", "abbreviation": "MATH", "title": "Math"}],
                 ns(), columns=["id", "abbreviation"])
        out = buf.getvalue()
        self.assertIn("MATH", out)
        self.assertIn("abbreviation", out)  # header printed

    def test_csv_mode_writes_file(self):
        path = os.path.join(tempfile.mkdtemp(), "out.csv")
        buf = io.StringIO()
        with redirect_stdout(buf):
            emit([{"id": "1", "abbreviation": "MATH"}],
                 ns(out=path), columns=["id", "abbreviation"])
        with open(path) as fh:
            content = fh.read()
        self.assertIn("id,abbreviation", content)
        self.assertIn("1,MATH", content)
        self.assertIn(path, buf.getvalue())  # confirmation line

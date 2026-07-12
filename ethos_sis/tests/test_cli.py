import io
import unittest
from contextlib import redirect_stderr
from unittest import mock

from ethos_sis import cli


class MainDispatchTest(unittest.TestCase):
    def test_no_args_errors(self):
        # argparse exits with code 2 when a required subcommand is missing
        with self.assertRaises(SystemExit) as ctx, redirect_stderr(io.StringIO()):
            cli.main([])
        self.assertEqual(ctx.exception.code, 2)

    def test_dispatches_to_command_func(self):
        called = {}

        def fake_register(subparsers):
            p = subparsers.add_parser("demo")
            p.set_defaults(func=lambda client, args: called.setdefault("ran", True) and 0)

        module = mock.Mock()
        module.register = fake_register
        with mock.patch.object(cli, "COMMAND_MODULES", [module]), \
             mock.patch.object(cli, "load_config"), \
             mock.patch.object(cli, "EthosClient"):
            rc = cli.main(["demo"])
        self.assertEqual(rc, 0)
        self.assertTrue(called.get("ran"))

    def test_permission_error_becomes_exit_1(self):
        def fake_register(subparsers):
            p = subparsers.add_parser("demo")

            def boom(client, args):
                raise PermissionError("nope")

            p.set_defaults(func=boom)

        module = mock.Mock()
        module.register = fake_register
        with mock.patch.object(cli, "COMMAND_MODULES", [module]), \
             mock.patch.object(cli, "load_config"), \
             mock.patch.object(cli, "EthosClient"), \
             redirect_stderr(io.StringIO()):
            rc = cli.main(["demo"])
        self.assertEqual(rc, 1)

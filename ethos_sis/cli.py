from __future__ import annotations

import argparse
import sys

import requests

from .client import EthosClient
from .commands import COMMAND_MODULES
from .config import load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ethos-sis",
        description="Query the Ellucian Ethos Integration API.",
    )
    subparsers = parser.add_subparsers(dest="domain", required=True)
    for module in COMMAND_MODULES:
        module.register(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()
    client = EthosClient(config)
    try:
        return args.func(client, args)
    except (PermissionError, RuntimeError, ValueError,
            requests.RequestException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

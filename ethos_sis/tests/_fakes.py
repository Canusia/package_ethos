"""Shared test doubles for command tests."""

import argparse


class FakeClient:
    """Stand-in for EthosClient; records calls, returns canned data."""

    def __init__(self, collection=None, entity=None):
        self._collection = collection if collection is not None else []
        self._entity = entity
        self.calls = []

    def get_collection(self, path, *, criteria=None, accept=None, extra_params=None):
        self.calls.append(
            ("collection", path, criteria, accept, extra_params)
        )
        return list(self._collection)

    def get_entity(self, path, key, accept=None):
        self.calls.append(("entity", path, key, accept))
        return self._entity


def ns(**kw):
    """Build an argparse.Namespace with output-flag defaults."""
    kw.setdefault("json", False)
    kw.setdefault("out", None)
    return argparse.Namespace(**kw)

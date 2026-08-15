"""Shared test doubles for command tests."""

import argparse


class FakeClient:
    """Stand-in for EthosClient; records calls, returns canned data."""

    def __init__(self, collection=None, entity=None, messages=None, remaining=0):
        self._collection = collection if collection is not None else []
        self._entity = entity
        self._messages = messages if messages is not None else []
        self._remaining = remaining
        self.calls = []

    def get_collection(self, path, *, criteria=None, accept=None, extra_params=None):
        self.calls.append(
            ("collection", path, criteria, accept, extra_params)
        )
        return list(self._collection)

    def get_entity(self, path, key, accept=None):
        self.calls.append(("entity", path, key, accept))
        return self._entity

    def consume_messages(self, *, limit=None, last_processed_id=None):
        self.calls.append(("consume", limit, last_processed_id))
        return list(self._messages), self._remaining

    def available_message_count(self):
        self.calls.append(("peek",))
        return self._remaining


def ns(**kw):
    """Build an argparse.Namespace with output-flag defaults."""
    kw.setdefault("json", False)
    kw.setdefault("out", None)
    return argparse.Namespace(**kw)

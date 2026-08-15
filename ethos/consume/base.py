"""The handler protocol.

Two phases, deliberately not a `dry_run=True` flag:

    plan(message)  -> Plan     pure; resolves the target and computes intent
    apply(message, plan) -> Result   performs the writes

A dry-run calls plan() only. A real consume calls plan() then apply(). One code
path computes the decision, so a dry-run cannot diverge from what a consume would
do. A flag instead would make every future handler author responsible for
checking it before each write — and the first one who forgets does a live write
from a dry-run button.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Change:
    """One intended field mutation, rendered as from -> to in the UI."""
    field: str
    old: str
    new: str


@dataclass
class Plan:
    """What a handler intends to do. Produced without writing anything."""
    action: str
    summary: str
    changes: List[Change] = field(default_factory=list)
    target_type: str = ''
    target_pk: str = ''
    target_label: str = ''
    blocked: bool = False
    reason: str = ''


@dataclass
class Result:
    """What a handler actually did."""
    action: str
    detail: str
    target_type: str = ''
    target_pk: str = ''
    target_label: str = ''


class ConsumeHandler:
    """Base class for resource-specific handlers.

    Subclasses set `resource_name` and implement both methods. Handlers must be
    idempotent: notifications reflect current state, not a delta, and each
    message is processed standalone — a failure at message 5 does not block
    message 6.
    """

    resource_name = ''

    def plan(self, message):
        """Return a Plan. MUST NOT write anything."""
        raise NotImplementedError

    def apply(self, message, plan):
        """Perform the writes described by `plan`. Return a Result."""
        raise NotImplementedError

"""Drain the Ethos change-notification queue into EthosMessage rows.

The poller ONLY stores. It never consumes — consuming is a separate, deliberate
step (see consume/service.py).

Critical property of /consume: a successful GET always advances Ethos's queue
pointer. `lastProcessedID` replays within the retention window; it does not hold
the pointer back. So each batch is persisted and the cursor advanced inside one
transaction: a crash before commit replays from the unchanged cursor.
"""

import logging

from django.db import transaction
from django.utils import timezone

from ..models import EthosMessage, EthosConsumeCursor
from .adapter import parse_notification
from . import config

logger = logging.getLogger(__name__)


def _get_client():
    from ..library.ethos import Ethos
    return Ethos()


@transaction.atomic
def _store_batch(records):
    """Persist one batch and advance the cursor. Atomic by design."""
    stored = duplicates = 0
    highest = None

    for raw in sorted(records, key=lambda r: int(r.get('id'))):
        fields = parse_notification(raw)
        queue_id = fields['queue_id']

        _msg, created = EthosMessage.objects.get_or_create(
            queue_id=queue_id, defaults=fields,
        )
        if created:
            stored += 1
        else:
            duplicates += 1

        highest = queue_id if highest is None else max(highest, queue_id)

    if highest is not None:
        cursor = EthosConsumeCursor.load()
        cursor.last_processed_id = max(cursor.last_processed_id, highest)
        cursor.last_polled_at = timezone.now()
        cursor.save()

    return stored, duplicates, highest


def poll(client=None, limit=None, max_batches=1, from_id=None):
    """Read up to `max_batches` batches and store them.

    from_id overrides the stored cursor — use it to replay after a failure.
    Returns {'stored', 'duplicates', 'batches', 'last_id'}.
    """
    client = client or _get_client()
    limit = limit or config.consume_limit()

    totals = {'stored': 0, 'duplicates': 0, 'batches': 0, 'last_id': None}

    for _ in range(max_batches):
        cursor_id = from_id if from_id is not None else EthosConsumeCursor.load().last_processed_id
        from_id = None  # only the first batch uses the override

        records, _log = client.get_messages(limit=limit, last_processed_id=cursor_id)
        totals['batches'] += 1

        if not records:
            break

        stored, duplicates, highest = _store_batch(records)
        totals['stored'] += stored
        totals['duplicates'] += duplicates
        if highest is not None:
            totals['last_id'] = highest

        if len(records) < limit:
            break

    return totals

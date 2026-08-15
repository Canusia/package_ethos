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
    """Persist one batch and advance the cursor. Atomic by design.

    `queue_id` is intentionally not unique at the DB layer (see the model), so
    duplicates are checked with exists()-then-create() rather than
    get_or_create() — get_or_create() would raise MultipleObjectsReturned if
    duplicate rows ever existed, instead of just ignoring them.
    """
    stored = duplicates = 0
    highest = None
    ids = [r.get('id') for r in records]

    try:
        for raw in sorted(records, key=lambda r: int(r.get('id'))):
            fields = parse_notification(raw)
            queue_id = fields['queue_id']

            if EthosMessage.objects.filter(queue_id=queue_id).exists():
                duplicates += 1
            else:
                EthosMessage.objects.create(**fields)
                stored += 1

            highest = queue_id if highest is None else max(highest, queue_id)

        if highest is not None:
            cursor = EthosConsumeCursor.load()
            cursor.last_processed_id = max(cursor.last_processed_id, highest)
            cursor.last_polled_at = timezone.now()
            cursor.save()
    except Exception:
        # Ethos's pointer has already advanced past this batch (see module
        # docstring) — this traceback is the only record of which ids were lost.
        logger.exception('Failed to store Ethos notification batch (ids=%s)', ids)
        raise

    return stored, duplicates, highest


def poll(client=None, limit=None, max_batches=1, from_id=None):
    """Read up to `max_batches` batches and store them.

    from_id overrides the stored cursor — use it to replay after a failure.
    A local high-water mark (not the persisted cursor) drives the id sent on
    each subsequent request within this call, so `--from-id 5 --max-batches 3`
    walks forward from 5 even if the stored cursor is already far ahead —
    re-reading the stored cursor each iteration would silently skip the very
    range the replay was asked to cover. The persisted cursor is still only
    ever advanced (never dragged backwards) via the max() clamp in
    `_store_batch`.

    Returns {'stored', 'duplicates', 'batches', 'last_id'}.
    """
    client = client or _get_client()
    limit = limit or config.consume_limit()

    totals = {'stored': 0, 'duplicates': 0, 'batches': 0, 'last_id': None}

    cursor_id = from_id if from_id is not None else EthosConsumeCursor.load().last_processed_id

    for _ in range(max_batches):
        records, _log = client.get_messages(limit=limit, last_processed_id=cursor_id)
        totals['batches'] += 1

        if not records:
            break

        stored, duplicates, highest = _store_batch(records)
        totals['stored'] += stored
        totals['duplicates'] += duplicates
        if highest is not None:
            totals['last_id'] = highest
            cursor_id = highest

        if len(records) < limit:
            break

    return totals

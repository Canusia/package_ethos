"""Dispatch one stored notification to its handler.

Failures mark the message `failed` and are NEVER retried automatically — the
message sits in the UI for a human to inspect and re-run, and a re-run
overwrites the single result. Messages are processed in queue order but stand
alone: a failure at message 5 does not block message 6, so handlers must be
idempotent.
"""

import logging
import traceback

from django.db import transaction
from django.utils import timezone

from ..models import EthosMessage
from .registry import get_handler

logger = logging.getLogger(__name__)


def _record(message, status, action='', detail='', error='', plan=None):
    message.status = status
    message.action = action
    message.action_detail = detail
    message.error = error
    message.consumed_at = timezone.now()
    if plan is not None:
        message.target_type = plan.target_type
        message.target_pk = plan.target_pk
        message.target_label = plan.target_label
    message.save()


def consume_message(message, dry_run=False, force=False):
    """Plan and (unless dry_run) apply one message.

    Returns the Plan in dry-run mode; otherwise returns the Plan that was acted
    on, or None when there was no handler or nothing to do.
    """
    if message.status != EthosMessage.PENDING and not force and not dry_run:
        return None

    handler = get_handler(message.resource_name)
    if handler is None:
        if dry_run:
            return None
        _record(message, EthosMessage.SKIPPED, action='no_handler',
                detail=f'No handler configured for {message.resource_name}')
        return None

    try:
        plan = handler.plan(message)
    except Exception as exc:
        if dry_run:
            raise
        logger.exception('plan() failed for EthosMessage %s', message.pk)
        _record(message, EthosMessage.FAILED, action='plan_failed',
                detail=str(exc), error=traceback.format_exc())
        return None

    if dry_run:
        return plan

    if plan.blocked:
        _record(message, EthosMessage.FLAGGED, action=plan.action,
                detail=plan.reason or plan.summary, plan=plan)
        return plan

    try:
        with transaction.atomic():
            result = handler.apply(message, plan)
    except Exception as exc:
        logger.exception('apply() failed for EthosMessage %s', message.pk)
        _record(message, EthosMessage.FAILED, action=plan.action,
                detail=str(exc), error=traceback.format_exc(), plan=plan)
        return plan

    _record(message, EthosMessage.CONSUMED, action=result.action,
            detail=result.detail, plan=plan)
    message.target_type = result.target_type or plan.target_type
    message.target_pk = result.target_pk or plan.target_pk
    message.target_label = result.target_label or plan.target_label
    message.save(update_fields=['target_type', 'target_pk', 'target_label'])
    return plan

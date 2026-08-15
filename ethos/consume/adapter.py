"""Translate an Ethos change-notification envelope into EthosMessage kwargs.

This module is the ONLY place that knows Ethos's field names. Everything
downstream reads model fields. If a tenant's envelope differs, fix it here and
re-extract from stored payloads with a data migration — nothing is lost at
capture time, because `payload` holds the notification verbatim.
"""

from django.utils.dateparse import parse_datetime


def _dt(value):
    """Parse an Ethos timestamp, tolerating both formats it emits.

    `published` is space-separated with a two-digit offset
    (`2026-08-12 20:48:04.702495+00`); `initiated` is ISO-8601 with `Z`.
    Django's parse_datetime handles both.
    """
    if not value:
        return None
    return parse_datetime(value)


def parse_notification(raw):
    """Return kwargs for EthosMessage(**kwargs) from one notification.

    Raises ValueError if the queue id is missing or non-numeric — that id is the
    cursor, so a notification without one cannot be safely stored.
    """
    queue_id = raw.get('id')
    if queue_id is None:
        raise ValueError('notification has no id')

    resource = raw.get('resource') or {}
    publisher = raw.get('publisher') or {}

    return {
        'queue_id':         int(queue_id),
        'published_on':     _dt(raw.get('published')),
        'resource_name':    resource.get('name') or '',
        'resource_id':      resource.get('id') or '',
        'resource_version': resource.get('version') or '',
        'operation':        raw.get('operation') or '',
        'content_type':     raw.get('contentType') or '',
        'message_type':     raw.get('messageType') or '',
        'sis_message_id':   raw.get('messageId') or '',
        'initiated_on':     _dt(raw.get('initiated')),
        'publisher_id':     publisher.get('id') or '',
        'payload':          raw,
    }

"""
Ethos models:
  - EthosLog: structured log of every Ethos API call
  - EthosApplication / EthosResource / EthosRepresentation: local cache of available resources
"""

from django.db import models

_ETHOS_BASE_URL = 'https://integrate.elluciancloud.com'


class EthosLog(models.Model):
    """Structured record of a single Ethos API call."""

    sent_on         = models.DateTimeField(auto_now_add=True, db_index=True)
    method          = models.CharField(max_length=10)                    # GET / POST / PUT
    url             = models.CharField(max_length=500, db_index=True)
    message_type    = models.CharField(max_length=100, db_index=True)    # free-text category
    description     = models.CharField(max_length=500, blank=True)
    request_headers = models.JSONField(default=dict)   # custom headers only — no Authorization token
    request_body    = models.JSONField(blank=True, null=True)
    response_status = models.IntegerField(null=True, db_index=True)
    response_body   = models.TextField(blank=True)

    class Meta:
        ordering = ['-sent_on']

    def __str__(self):
        return f"{self.method} {self.path} [{self.response_status}]"

    @property
    def success(self):
        return self.response_status is not None and 200 <= self.response_status < 300

    @property
    def path(self):
        return self.url.replace(_ETHOS_BASE_URL, '') or self.url

    @property
    def response_json(self):
        """Parsed response_body as a dict, or {} on parse failure."""
        import json
        if not self.response_body:
            return {}
        try:
            return json.loads(self.response_body)
        except (ValueError, TypeError):
            return {}

    @property
    def error_message(self):
        """Best-effort short error string from response_body for failed calls."""
        if self.success:
            return ''
        body = self.response_json
        if isinstance(body, dict):
            errs = body.get('errors')
            if isinstance(errs, list) and errs and isinstance(errs[0], dict):
                msg = errs[0].get('message')
                if msg:
                    return str(msg)[:500]
            msg = body.get('message')
            if msg:
                return str(msg)[:500]
        return (self.response_body or '')[:500]


class EthosApplication(models.Model):
    """A top-level Ethos application/integration (e.g. 'CRM Advise Test')."""

    ethos_id = models.CharField(max_length=100, unique=True)  # GUID from API
    name = models.CharField(max_length=200)
    about = models.JSONField(default=list)   # [{"name": "Advise API", "version": "4.1.0.0"}]
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class EthosResource(models.Model):
    """A single API resource (endpoint) belonging to an Ethos application."""

    application = models.ForeignKey(
        EthosApplication,
        on_delete=models.CASCADE,
        related_name='resources',
    )
    name = models.CharField(max_length=200, db_index=True)  # e.g. "advise-advisor-types"
    preferred_representation = models.ForeignKey(
        'EthosRepresentation',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    class Meta:
        unique_together = [('application', 'name')]
        ordering = ['name']

    def __str__(self):
        return self.name


class EthosRepresentation(models.Model):
    """A representation of an Ethos resource: one media type + its supported methods/version/filters."""

    resource = models.ForeignKey(
        EthosResource,
        on_delete=models.CASCADE,
        related_name='representations',
    )
    x_media_type = models.CharField(max_length=300)        # e.g. "application/vnd.hedtech.integration.v1+json"
    methods = models.JSONField(default=list)                # e.g. ["get"] or ["get", "post"]
    version = models.CharField(max_length=50, blank=True, null=True)  # e.g. "v1", "v13.1.0"
    filters = models.JSONField(default=list)               # e.g. ["code", "number", "academicPeriod"]
    deprecation_notice = models.JSONField(blank=True, null=True)  # {"deprecatedOn": "...", "description": "...", "sunsetOn": "..."}

    class Meta:
        ordering = ['-version']

    def __str__(self):
        return f"{self.resource.name} — {self.x_media_type}"


class EthosMessage(models.Model):
    """A single Ethos change-notification, with its consume result."""

    PENDING  = 'pending'
    CONSUMED = 'consumed'
    FAILED   = 'failed'
    SKIPPED  = 'skipped'
    FLAGGED  = 'flagged'

    STATUS_CHOICES = [
        (PENDING,  'Pending'),
        (CONSUMED, 'Consumed'),
        (FAILED,   'Failed'),
        (SKIPPED,  'Skipped'),
        (FLAGGED,  'Flagged'),
    ]

    # --- envelope -------------------------------------------------------
    queue_id         = models.BigIntegerField(db_index=True)          # Ethos `id`, not a GUID
    published_on     = models.DateTimeField(null=True, blank=True, db_index=True)
    received_on      = models.DateTimeField(auto_now_add=True, db_index=True)
    resource_name    = models.CharField(max_length=100, db_index=True)
    resource_id      = models.CharField(max_length=64, db_index=True)
    resource_version = models.CharField(max_length=200, blank=True)
    operation        = models.CharField(max_length=20, db_index=True)
    content_type     = models.CharField(max_length=50, blank=True)
    message_type     = models.CharField(max_length=50, blank=True)
    sis_message_id   = models.CharField(max_length=50, blank=True)    # optional `messageId`
    initiated_on     = models.DateTimeField(null=True, blank=True)    # optional `initiated`
    publisher_id     = models.CharField(max_length=64, blank=True)
    payload          = models.JSONField(default=dict)                 # the whole notification, verbatim

    # --- consume result (single, overwritten on re-run) -----------------
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                     default=PENDING, db_index=True)
    consumed_at   = models.DateTimeField(null=True, blank=True, db_index=True)
    action        = models.CharField(max_length=50, blank=True)
    action_detail = models.TextField(blank=True)
    error         = models.TextField(blank=True)
    target_type   = models.CharField(max_length=100, blank=True)   # e.g. 'cis.StudentRegistration'
    target_pk     = models.CharField(max_length=64, blank=True)
    target_label  = models.CharField(max_length=255, blank=True)   # survives target deletion

    class Meta:
        ordering = ['-queue_id']
        indexes = [
            models.Index(fields=['resource_name', 'status']),
        ]

    def __str__(self):
        return f"#{self.queue_id} {self.resource_name} {self.operation} [{self.status}]"

    @property
    def is_pending(self):
        return self.status == self.PENDING

    @property
    def content(self):
        """The resource body carried by the notification."""
        return (self.payload or {}).get('content') or {}

    @property
    def status_reason(self):
        """`sectionRegistrationStatusReason` when present — the real action signal."""
        return (self.content.get('status') or {}).get('sectionRegistrationStatusReason') or ''


class EthosConsumeCursor(models.Model):
    """Singleton queue pointer.

    Deliberately a table rather than MAX(queue_id) over EthosMessage: retention
    deletes rows, and a cursor derived from a purged table would replay the whole
    retention window after the first purge.
    """

    last_processed_id = models.BigIntegerField(default=0)
    last_polled_at    = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"cursor@{self.last_processed_id}"

    @classmethod
    def load(cls):
        cursor = cls.objects.order_by('pk').first()
        if cursor is None:
            cursor = cls.objects.create()
        return cursor

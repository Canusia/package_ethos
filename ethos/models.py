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

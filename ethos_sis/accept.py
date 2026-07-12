"""Per-resource Accept (x-media-type) media types.

The Django app resolves these from the DB (EthosResource.preferred_representation).
The standalone CLI uses the same hardcoded fallbacks the mixins fall back to.
"""

RESOURCE_MEDIA_TYPES = {
    "sections": "application/vnd.hedtech.integration.sections-maximum.v16+json",
    "person-holds": "application/vnd.hedtech.integration.v6+json",
    "section-registrations": "application/vnd.hedtech.integration.v16+json",
    "student-academic-programs": "application/vnd.hedtech.integration.v17+json",
}

DEFAULT_MEDIA_TYPE = "application/json"


def accept_for(resource: str, override: str | None = None) -> str:
    if override:
        return override
    return RESOURCE_MEDIA_TYPES.get(resource, DEFAULT_MEDIA_TYPE)

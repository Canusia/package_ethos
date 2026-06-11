"""Pin the status.detail.id resolution + payload behavior of RegistrationMixin."""

from unittest.mock import patch, MagicMock
from django.test import TestCase

try:
    from ethos.ethos.library.ethos import Ethos
    from ethos.ethos.models import EthosLog
except ImportError:
    from ethos.library.ethos import Ethos
    from ethos.models import EthosLog


CONFIGURED_STATUSES = [
    {
        "status": {
            "registrationStatus": "registered",
            "sectionRegistrationStatusReason": "registered",
        },
        "headcountStatus": "exclude",
        "code": "N",
        "title": "New",
        "description": "New",
        "id": "d047c950-1f34-4541-8796-837fbffcf745",
    },
    {
        "status": {
            "registrationStatus": "notRegistered",
            "sectionRegistrationStatusReason": "dropped",
        },
        "headcountStatus": "exclude",
        "code": "D",
        "title": "Dropped",
        "description": "Dropped",
        "id": "11111111-2222-3333-4444-555555555555",
    },
]


class StatusDetailIdResolverTests(TestCase):

    def setUp(self):
        self.ethos = Ethos()

    def test_returns_configured_id_when_match_present(self):
        guids = {"section_registration_statuses": CONFIGURED_STATUSES}
        self.assertEqual(
            self.ethos._status_detail_id("registered", guids),
            "d047c950-1f34-4541-8796-837fbffcf745",
        )

    def test_matches_on_section_registration_status_reason(self):
        guids = {"section_registration_statuses": CONFIGURED_STATUSES}
        self.assertEqual(
            self.ethos._status_detail_id("dropped", guids),
            "11111111-2222-3333-4444-555555555555",
        )

    def test_falls_back_to_default_registered_guid_when_absent(self):
        guids = {}
        self.assertEqual(
            self.ethos._status_detail_id("registered", guids),
            "a4bdb5fe-3568-4b97-ad77-48987c78965f",
        )

    def test_returns_none_for_unknown_status_without_match_or_default(self):
        guids = {"section_registration_statuses": CONFIGURED_STATUSES}
        self.assertIsNone(self.ethos._status_detail_id("withdrawn", guids))

    def test_loads_guids_from_db_when_not_passed(self):
        with patch.object(self.ethos, '_load_sis_guids',
                          return_value={"section_registration_statuses": CONFIGURED_STATUSES}):
            self.assertEqual(
                self.ethos._status_detail_id("registered"),
                "d047c950-1f34-4541-8796-837fbffcf745",
            )

    def test_skips_matching_entry_with_empty_id_and_falls_back(self):
        guids = {"section_registration_statuses": [
            {"status": {"sectionRegistrationStatusReason": "registered"}, "id": ""},
        ]}
        self.assertEqual(
            self.ethos._status_detail_id("registered", guids),
            "a4bdb5fe-3568-4b97-ad77-48987c78965f",
        )

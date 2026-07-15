"""Pin the status.detail.id resolution + payload behavior of RegistrationMixin."""

from unittest.mock import patch, MagicMock
from django.test import TestCase

try:
    from ethos.ethos.library.ethos import Ethos
except ImportError:
    from ethos.library.ethos import Ethos


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


class MirrorRegistrationCreatePayloadTests(TestCase):

    def setUp(self):
        self.ethos = Ethos()
        auth = patch.object(self.ethos, 'get_auth_token', return_value='fake')
        auth.start()
        self.addCleanup(auth.stop)

    def _fake_response(self):
        resp = MagicMock()
        resp.ok = True
        resp.status_code = 201
        resp.json.return_value = {'id': '00000000-0000-0000-0000-000000000001'}
        resp.text = '{"id": "00000000-0000-0000-0000-000000000001"}'
        return resp

    @patch('ethos.ethos.library.registration.requests.post')
    def test_create_attaches_configured_detail_id(self, mock_post):
        mock_post.return_value = self._fake_response()
        with patch.object(self.ethos, '_load_sis_guids',
                          return_value={"section_registration_statuses": CONFIGURED_STATUSES}):
            self.ethos.mirror_registration(
                student_sis_id='S1', section_id='SEC1',
                status='registered', registration_id=None,
            )
        sent = mock_post.call_args.kwargs['json']
        self.assertEqual(
            sent['status']['detail']['id'],
            'd047c950-1f34-4541-8796-837fbffcf745',
        )
        self.assertEqual(sent['status']['registrationStatus'], 'registered')
        self.assertEqual(sent['status']['sectionRegistrationStatusReason'], 'registered')

    @patch('ethos.ethos.library.registration.requests.post')
    def test_create_maps_dropped_reason_to_not_registered(self, mock_post):
        mock_post.return_value = self._fake_response()
        with patch.object(self.ethos, '_load_sis_guids',
                          return_value={"section_registration_statuses": CONFIGURED_STATUSES}):
            self.ethos.mirror_registration(
                student_sis_id='S1', section_id='SEC1',
                status='dropped', registration_id=None,
            )
        sent = mock_post.call_args.kwargs['json']
        # A non-registered reason must send registrationStatus='notRegistered',
        # not the reason itself.
        self.assertEqual(sent['status']['registrationStatus'], 'notRegistered')
        self.assertEqual(sent['status']['sectionRegistrationStatusReason'], 'dropped')
        self.assertEqual(
            sent['status']['detail']['id'],
            '11111111-2222-3333-4444-555555555555',
        )

    @patch('ethos.ethos.library.registration.requests.post')
    def test_create_maps_withdrawn_reason_to_not_registered(self, mock_post):
        mock_post.return_value = self._fake_response()
        with patch.object(self.ethos, '_load_sis_guids', return_value={}):
            self.ethos.mirror_registration(
                student_sis_id='S1', section_id='SEC1',
                status='withdrawn', registration_id=None,
            )
        sent = mock_post.call_args.kwargs['json']
        self.assertEqual(sent['status']['registrationStatus'], 'notRegistered')
        self.assertEqual(sent['status']['sectionRegistrationStatusReason'], 'withdrawn')

    @patch('ethos.ethos.library.registration.requests.post')
    def test_create_uses_fallback_registered_guid(self, mock_post):
        mock_post.return_value = self._fake_response()
        with patch.object(self.ethos, '_load_sis_guids', return_value={}):
            self.ethos.mirror_registration(
                student_sis_id='S1', section_id='SEC1',
                status='registered', registration_id=None,
            )
        sent = mock_post.call_args.kwargs['json']
        self.assertEqual(
            sent['status']['detail']['id'],
            'a4bdb5fe-3568-4b97-ad77-48987c78965f',
        )

    @patch('ethos.ethos.library.registration.requests.post')
    def test_create_omits_detail_when_no_match_and_no_default(self, mock_post):
        mock_post.return_value = self._fake_response()
        with patch.object(self.ethos, '_load_sis_guids', return_value={}):
            self.ethos.mirror_registration(
                student_sis_id='S1', section_id='SEC1',
                status='withdrawn', registration_id=None,
            )
        sent = mock_post.call_args.kwargs['json']
        self.assertNotIn('detail', sent['status'])


class UpdateRegistrationPayloadTests(TestCase):

    def setUp(self):
        self.ethos = Ethos()
        auth = patch.object(self.ethos, 'get_auth_token', return_value='fake')
        auth.start()
        self.addCleanup(auth.stop)

    def _fake_response(self):
        resp = MagicMock()
        resp.ok = True
        resp.status_code = 200
        resp.json.return_value = {'id': 'REG1'}
        resp.text = '{"id": "REG1"}'
        return resp

    @patch('ethos.ethos.library.registration.requests.put')
    def test_update_attaches_detail_id_by_reason_match(self, mock_put):
        mock_put.return_value = self._fake_response()
        with patch.object(self.ethos, '_load_sis_guids',
                          return_value={"section_registration_statuses": CONFIGURED_STATUSES}):
            self.ethos.update_registration(
                student_sis_id='S1', section_id='SEC1',
                status='dropped', registration_id='REG1',
            )
        sent = mock_put.call_args.kwargs['json']
        # registrationStatus stays the literal 'notRegistered' on the update path;
        # the detail id is resolved via sectionRegistrationStatusReason == status.
        self.assertEqual(sent['status']['registrationStatus'], 'notRegistered')
        self.assertEqual(sent['status']['sectionRegistrationStatusReason'], 'dropped')
        self.assertEqual(
            sent['status']['detail']['id'],
            '11111111-2222-3333-4444-555555555555',
        )

    @patch('ethos.ethos.library.registration.requests.put')
    def test_update_omits_detail_when_no_match_and_no_default(self, mock_put):
        mock_put.return_value = self._fake_response()
        with patch.object(self.ethos, '_load_sis_guids', return_value={}):
            self.ethos.update_registration(
                student_sis_id='S1', section_id='SEC1',
                status='withdrawn', registration_id='REG1',
            )
        sent = mock_put.call_args.kwargs['json']
        self.assertNotIn('detail', sent['status'])

    @patch('ethos.ethos.library.registration.requests.put')
    def test_update_uses_fallback_registered_guid(self, mock_put):
        mock_put.return_value = self._fake_response()
        with patch.object(self.ethos, '_load_sis_guids', return_value={}):
            self.ethos.update_registration(
                student_sis_id='S1', section_id='SEC1',
                status='registered', registration_id='REG1',
            )
        sent = mock_put.call_args.kwargs['json']
        self.assertEqual(
            sent['status']['detail']['id'],
            'a4bdb5fe-3568-4b97-ad77-48987c78965f',
        )

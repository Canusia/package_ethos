"""#15: SPAIDEN emergency-contact API on PersonMixin."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from ethos.ethos.library.ethos import Ethos
from ethos.ethos.library.person import (
    EMERGENCY_CONTACT_MEDIA, EMERGENCY_CONTACT_POST_MEDIA, split_phone,
)

URL = 'https://integrate.elluciancloud.com/api/general-person-identification-emergency-contact'
ROW = {'priority': '1', 'firstName': 'Pat', 'lastName': 'Lee',
       'phoneArea': '518', 'phoneNumber': '7432557', 'phoneExt': '12', 'reltCode': 'T'}


def _student(psid='01070122'):
    return SimpleNamespace(id=7, user=SimpleNamespace(psid=psid))


def _resp(ok=True, body=None):
    resp = MagicMock()
    resp.ok = ok
    resp.json.return_value = body
    return resp


class EmergencyContactTestBase(SimpleTestCase):

    def setUp(self):
        self.eth = Ethos.__new__(Ethos)
        patcher = patch.object(self.eth, '_api_request')
        self.api = patcher.start()
        self.addCleanup(patcher.stop)
        self.log = MagicMock(name='log')

    def call(self):
        args, kwargs = self.api.call_args
        return args, kwargs


class SplitPhoneTests(SimpleTestCase):

    def test_us_number(self):
        self.assertEqual(split_phone('(518) 743-2557'), ('518', '7432557'))

    def test_leading_country_code(self):
        self.assertEqual(split_phone('+1 518.743.2557'), ('518', '7432557'))

    def test_not_ten_digits(self):
        self.assertEqual(split_phone('743-2557'), ('', '7432557'))
        self.assertEqual(split_phone('44 20 7946 0958 123'), ('', '442079460958'))

    def test_empty(self):
        self.assertEqual(split_phone(None), ('', ''))
        self.assertEqual(split_phone(''), ('', ''))


class ListTests(EmergencyContactTestBase):

    def test_get_by_banner_id(self):
        self.api.return_value = (_resp(body=[ROW]), self.log)
        rows, ok, log = self.eth.list_emergency_contacts(_student())
        self.assertEqual((rows, ok, log), ([ROW], True, self.log))
        args, kwargs = self.call()
        self.assertEqual(args[:3], ('GET', f'{URL}?id=01070122', 'emergency_contact_lookup'))
        self.assertEqual(kwargs['headers'], {'Accept': EMERGENCY_CONTACT_MEDIA})
        self.assertIsNone(kwargs['data'])

    def test_error_is_not_ok(self):
        self.api.return_value = (_resp(ok=False), self.log)
        self.assertEqual(self.eth.list_emergency_contacts(_student()), ([], False, self.log))

    def test_non_list_body_is_not_ok(self):
        self.api.return_value = (_resp(body={'errors': []}), self.log)
        self.assertEqual(self.eth.list_emergency_contacts(_student()), ([], False, self.log))

    def test_no_banner_id_sends_nothing(self):
        self.assertEqual(self.eth.list_emergency_contacts(_student(psid='')), ([], False, None))
        self.api.assert_not_called()


class CreateTests(EmergencyContactTestBase):

    def test_post_v1_0_0_without_empty_fields(self):
        self.api.return_value = (_resp(), self.log)
        fields = {'firstName': 'Pat', 'lastName': 'Lee', 'phoneArea': '518',
                  'phoneNumber': '7432557', 'phoneExt': '', 'reltCode': 'T'}
        self.assertEqual(self.eth.create_emergency_contact(_student(), fields, priority=2),
                         ('2', self.log))
        args, kwargs = self.call()
        self.assertEqual(args[:3], ('POST', URL, 'emergency_contact_create'))
        self.assertEqual(kwargs['headers'], {'Accept': EMERGENCY_CONTACT_POST_MEDIA,
                                             'Content-Type': EMERGENCY_CONTACT_POST_MEDIA})
        self.assertEqual(json.loads(kwargs['data']), {
            'id': '01070122', 'priority': '2', 'firstName': 'Pat', 'lastName': 'Lee',
            'phoneArea': '518', 'phoneNumber': '7432557', 'reltCode': 'T'})

    def test_fields_cannot_override_id_or_priority(self):
        self.api.return_value = (_resp(), self.log)
        self.eth.create_emergency_contact(
            _student(), {'id': 'X', 'priority': '9', 'firstName': 'Pat', 'lastName': 'Lee'})
        body = json.loads(self.call()[1]['data'])
        self.assertEqual((body['id'], body['priority']), ('01070122', '1'))

    def test_error_returns_none(self):
        self.api.return_value = (_resp(ok=False), self.log)
        self.assertEqual(self.eth.create_emergency_contact(
            _student(), {'firstName': 'Pat', 'lastName': 'Lee'}), (None, self.log))

    def test_no_banner_id_sends_nothing(self):
        self.assertEqual(self.eth.create_emergency_contact(_student(psid=None), {}), (None, None))
        self.api.assert_not_called()


class UpdateTests(EmergencyContactTestBase):

    def test_put_v1_1_0_with_criteria_and_cleared_fields(self):
        self.api.return_value = (_resp(body=[ROW]), self.log)
        fields = {'firstName': 'Pat', 'lastName': 'Lee-Smith', 'phoneArea': '518',
                  'phoneNumber': '7432557', 'phoneExt': '', 'reltCode': 'T'}
        self.assertEqual(self.eth.update_emergency_contact(_student(), ROW, fields),
                         ('1', self.log))
        args, kwargs = self.call()
        self.assertEqual(args[:3], ('PUT', URL, 'emergency_contact_update'))
        self.assertEqual(kwargs['headers'], {'Accept': EMERGENCY_CONTACT_MEDIA,
                                             'Content-Type': EMERGENCY_CONTACT_MEDIA})
        self.assertEqual(json.loads(kwargs['data']), {
            'id': '01070122',
            'criteria.priority': '1', 'criteria.firstName': 'Pat', 'criteria.lastName': 'Lee',
            'priority': '1', 'firstName': 'Pat', 'lastName': 'Lee-Smith',
            'phoneArea': '518', 'phoneNumber': '7432557', 'phoneExt': '', 'reltCode': 'T'})

    def test_required_values_default_to_existing_row(self):
        self.api.return_value = (_resp(), self.log)
        self.eth.update_emergency_contact(_student(), ROW, {'phoneExt': None})
        body = json.loads(self.call()[1]['data'])
        self.assertEqual((body['priority'], body['firstName'], body['lastName'], body['phoneExt']),
                         ('1', 'Pat', 'Lee', ''))

    def test_fields_cannot_change_the_criteria(self):
        self.api.return_value = (_resp(), self.log)
        self.eth.update_emergency_contact(
            _student(), ROW, {'criteria.priority': '3', 'id': 'X', 'firstName': 'Sam'})
        body = json.loads(self.call()[1]['data'])
        self.assertEqual((body['criteria.priority'], body['id'], body['firstName']),
                         ('1', '01070122', 'Sam'))

    def test_error_returns_none(self):
        self.api.return_value = (_resp(ok=False), self.log)
        self.assertEqual(self.eth.update_emergency_contact(_student(), ROW, {}), (None, self.log))

    def test_no_banner_id_sends_nothing(self):
        self.assertEqual(self.eth.update_emergency_contact(_student(psid=''), ROW, {}),
                         (None, None))
        self.api.assert_not_called()

    def test_existing_row_without_priority_sends_nothing(self):
        self.assertEqual(self.eth.update_emergency_contact(
            _student(), {'firstName': 'Pat', 'lastName': 'Lee'}, {'phoneExt': ''}), (None, None))
        self.api.assert_not_called()

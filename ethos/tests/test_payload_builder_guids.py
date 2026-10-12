"""package_ethos#3 (1, 2): payload builders send no foreign placeholder GUIDs.

A missing guids key must be visible (null / omitted), never another college's
GUID, and a key may be stored as "<guid>" or {"id": "<guid>"}.
"""
import datetime
import importlib.util
import json
import re
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
    from ethos.ethos.library.base import EthosBase
else:  # pragma: no cover - flat pip layout
    from ethos.library.ethos import Ethos
    from ethos.library.base import EthosBase

GUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
NIL = '00000000-0000-0000-0000-000000000000'
SIS_ID = '11111111-2222-3333-4444-555555555555'


def _student(**overrides):
    user = SimpleNamespace(
        first_name='Ada', middle_name='B', last_name='Lovelace', address1='1 Main St',
        city='Spokane', state='WA', postal_code='99201', primary_phone='+1 (509) 555-1212',
        secondary_phone='509.555.3434', email='ada@example.com',
        date_of_birth=datetime.date(2009, 1, 2), ssn='', created_at=datetime.datetime(2026, 1, 1))
    student = SimpleNamespace(
        user=user, sis_race_codes=[], hispanic=False, citizenship_status='', parent_phone='1-509-555-5656',
        parent_email='parent@example.com', sis_id=SIS_ID, parent_first_name='Pat',
        parent_last_name='Lovelace', admission_id='adm-1', get_gender_code=lambda: 'F')
    for key, value in overrides.items():
        setattr(student, key, value)
    return student


def _foreign_guids(payload):
    """Every GUID in the payload that is not the nil id or the student's own id."""
    return set(GUID_RE.findall(payload)) - {NIL, SIS_ID, 'period-guid'}


@override_settings(MULTI_CAMPUS=False)
@patch.object(Ethos, '_load_sis_guids', return_value={})
class NoPlaceholderGuidsTests(SimpleTestCase):
    def test_person_json(self, _guids):
        self.assertEqual(_foreign_guids(Ethos().studentPersonJSON(_student())), set())

    def test_matching_json_sends_null_types(self, _guids):
        body = json.loads(Ethos().studentJSON(_student()))
        self.assertIsNone(body['phone']['type']['id'])
        self.assertIsNone(body['email']['type']['id'])
        self.assertIsNone(body['address']['type']['id'])

    def test_emergency_contact_omits_unset_type_and_relationship(self, _guids):
        contact = json.loads(Ethos().studentEmergencyContactJSON(_student()))['contact']
        self.assertNotIn('types', contact)
        self.assertNotIn('relationship', contact)

    @patch('cis.utils.active_term', return_value=SimpleNamespace(code='202690'))
    @patch.object(Ethos, 'get_academic_period_id', return_value='period-guid')
    def test_admission_json_sends_null_not_foreign(self, _period, _term, _guids):
        payload = Ethos().studentAdmissionJSON(_student())
        self.assertEqual(_foreign_guids(payload), set())
        body = json.loads(payload)
        self.assertIsNone(body['admissionPopulation']['id'])
        self.assertIsNone(body['type']['id'])
        self.assertIsNone(body['residencyType']['id'])
        self.assertIsNone(body['applicationAcademicPrograms'][0]['program']['id'])
        self.assertIsNone(body['applicationAcademicPrograms'][0]['academicLevel']['id'])

    def test_admission_decision_sends_null(self, _guids):
        body = json.loads(Ethos().studentAdmissionDecisionJSON(_student()))
        self.assertIsNone(body['decisionType']['id'])


@override_settings(MULTI_CAMPUS=False)
class GuidShapeTests(SimpleTestCase):
    def test_both_shapes_are_read(self):
        self.assertEqual(EthosBase._guid_setting({'k': 'g1'}, 'k'), 'g1')
        self.assertEqual(EthosBase._guid_setting({'k': {'id': 'g2'}}, 'k'), 'g2')
        self.assertIsNone(EthosBase._guid_setting({'k': ''}, 'k'))
        self.assertIsNone(EthosBase._guid_setting({'k': {}}, 'k'))
        self.assertIsNone(EthosBase._guid_setting({}, 'k'))

    @patch('cis.utils.active_term', return_value=SimpleNamespace(code='202690'))
    @patch.object(Ethos, 'get_academic_period_id', return_value='period-guid')
    def test_admission_accepts_either_shape_for_every_key(self, _period, _term):
        guids = {'admission_population': {'id': 'ap'}, 'student_type': 'st',
                 'residency_type': {'id': 'rt'}, 'program': 'pg', 'academic_level': 'al'}
        with patch.object(Ethos, '_load_sis_guids', return_value=guids):
            body = json.loads(Ethos().studentAdmissionJSON(_student()))
        self.assertEqual(body['admissionPopulation']['id'], 'ap')
        self.assertEqual(body['type']['id'], 'st')
        self.assertEqual(body['residencyType']['id'], 'rt')
        self.assertEqual(body['applicationAcademicPrograms'][0]['program']['id'], 'pg')
        self.assertEqual(body['applicationAcademicPrograms'][0]['academicLevel']['id'], 'al')

    def test_decision_type_dict_shape(self):
        with patch.object(Ethos, '_load_sis_guids', return_value={'decision_type': {'id': 'dt'}}):
            body = json.loads(Ethos().studentAdmissionDecisionJSON(_student()))
        self.assertEqual(body['decisionType']['id'], 'dt')

    def test_emergency_contact_reads_configured_type_and_relationship(self):
        guids = {'emergency_contact_type': 'ect', 'emergency_contact_relationship': 'Parent'}
        with patch.object(Ethos, '_load_sis_guids', return_value=guids):
            contact = json.loads(Ethos().studentEmergencyContactJSON(_student()))['contact']
        self.assertEqual(contact['types'], [{'id': 'ect'}])
        self.assertEqual(contact['relationship'], {'type': 'Parent'})


@override_settings(MULTI_CAMPUS=False)
@patch.object(Ethos, '_load_sis_guids', return_value={})
class PhoneDigitsTests(SimpleTestCase):
    def test_helper(self, _guids):
        self.assertEqual(EthosBase._phone_digits('+1 (509) 555-1212'), '5095551212')
        self.assertEqual(EthosBase._phone_digits('509.555.1212'), '5095551212')
        self.assertEqual(EthosBase._phone_digits('1-509-555-1212'), '5095551212')
        self.assertEqual(EthosBase._phone_digits(None), '')

    def test_builders_send_digits(self, _guids):
        person = json.loads(Ethos().studentPersonJSON(_student()))
        self.assertEqual([p['number'] for p in person['phones']],
                         ['5095551212', '5095553434', '5095555656'])
        self.assertEqual(json.loads(Ethos().studentJSON(_student()))['phone']['number'], '5095551212')
        contact = json.loads(Ethos().studentEmergencyContactJSON(_student()))['contact']
        self.assertEqual(contact['phones'], [{'number': '5095555656'}])

    def test_matching_json_omits_phone_when_none(self, _guids):
        student = _student()
        student.user.primary_phone = None
        self.assertNotIn('phone', json.loads(Ethos().studentJSON(student)))

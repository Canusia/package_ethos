"""package_ethos#3 (5): validate_person_match rules. Ported from SCCC.

Each test pins a rule to the Banner error it was derived from, so a change in behaviour
shows up as a failing assertion rather than as a silently weaker check.
"""
import importlib.util
from datetime import date, timedelta

from django.test import SimpleTestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.management.commands.validate_person_match import Command, CONTACT_TYPES
else:  # pragma: no cover - flat pip layout
    from ethos.management.commands.validate_person_match import Command, CONTACT_TYPES

PHONE_GUID = '48b711f8-1aa4-4bf6-83a0-9e906a40132e'


def _address(region='US-NY', type_id='a-ma'):
    return {'type': {'id': type_id}, 'addressLines': ['88 Lake Hill Rd'],
            'place': {'country': {'code': 'USA', 'locality': 'Burnt Hills',
                                  'region': {'code': region}, 'postalCode': '12027'}}}


class RuleTests(SimpleTestCase):
    def setUp(self):
        self.cmd = Command()

    def test_names(self):
        check = self.cmd._check_names({'firstName': 'Sue'})
        self.assertFalse(check.ok)
        self.assertEqual(check.banner_error, 'Legal first name and last name are required')
        self.assertTrue(self.cmd._check_names({'firstName': 'Sue', 'lastName': 'Neary'}).ok)

    def test_dob(self):
        self.assertEqual(self.cmd._check_dob({'dateOfBirth': '13/12/2010'}).banner_error,
                         'Invalid date format [dateOfBirth]')
        self.assertFalse(self.cmd._check_dob({}).ok)
        future = (date.today() + timedelta(days=1)).isoformat()
        check = self.cmd._check_dob({'dateOfBirth': future})
        self.assertFalse(check.ok)
        self.assertEqual(check.banner_error, 'Date of Birth cannot be a future date')
        self.assertTrue(self.cmd._check_dob({'dateOfBirth': '2010-12-13'}).ok)

    def test_enumerations(self):
        self.assertEqual(self.cmd._check_gender('banana').banner_error,
                         'Invalid enumeration value for [gender]')
        for value in ('male', 'female', 'unknown'):
            self.assertTrue(self.cmd._check_gender(value).ok, value)
        self.assertFalse(self.cmd._check_credential({'type': 'bogusType'}).ok)
        self.assertTrue(self.cmd._check_credential({'type': 'ssn', 'value': 'abc'}).ok)

    def test_email_and_region(self):
        self.assertFalse(self.cmd._check_email_address({'address': 'not-an-email'}).ok)
        self.assertTrue(self.cmd._check_email_address({'address': 'a@b.com'}).ok)
        self.assertIn('STVSTAT', self.cmd._check_region(_address(region='Washington')).banner_error)
        check = self.cmd._check_region(_address(region='US-ZZ'))
        self.assertTrue(check.ok)
        self.assertTrue(check.warning)  # well formed is not "will work"


class ContactTypeRuleTests(SimpleTestCase):
    def setUp(self):
        self.cmd = Command()
        self.tables = {'phone_type': ([{'id': PHONE_GUID, 'code': 'CE', 'title': 'Cell'}], None)}

    def test_missing_guid_is_reported_as_a_null_id(self):
        check = self.cmd._check_type('phone', {'type': {'id': None}}, 'phone_type', self.tables, False)
        self.assertFalse(check.ok)
        self.assertIn('phone_type', check.detail)
        self.assertIn('null', check.detail)

    def test_guid_absent_from_the_table_fails(self):
        check = self.cmd._check_type('phone', {'type': {'id': 'dead'}}, 'phone_type', self.tables, False)
        self.assertFalse(check.ok)
        self.assertEqual(check.banner_error, 'Phone type not found')

    def test_guid_in_the_table_reports_its_code(self):
        check = self.cmd._check_type('phone', {'type': {'id': PHONE_GUID}}, 'phone_type', self.tables, False)
        self.assertTrue(check.ok)
        self.assertIn('CE', check.detail)

    def test_unreadable_table_warns_rather_than_failing(self):
        tables = {'phone_type': ([], 'HTTP 403: Access is denied')}
        check = self.cmd._check_type('phone', {'type': {'id': PHONE_GUID}}, 'phone_type', tables, False)
        self.assertTrue(check.ok)
        self.assertTrue(check.warning)

    def test_offline_does_not_claim_verification(self):
        check = self.cmd._check_type('phone', {'type': {'id': PHONE_GUID}}, 'phone_type', {}, True)
        self.assertTrue(check.warning)
        self.assertIn('not verified', check.detail)

    def test_every_contact_type_declares_a_banner_error(self):
        for key, (endpoint, error) in CONTACT_TYPES.items():
            self.assertTrue(endpoint, key)
            self.assertIn('not found', error, key)


class PayloadShapeTests(SimpleTestCase):
    """The packaged studentJSON puts phone/email/address at the top level; SCCC's override
    nests them under matchingCriteria. Both are checked."""

    def _names(self, checks):
        return [c.name for c in checks]

    def _payload(self, nested):
        blocks = {'phone': {'type': {'id': None}, 'number': '5095551212'},
                  'email': {'type': {'id': 'e'}, 'address': 'a@b.com'},
                  'address': _address()}
        payload = {'names': {'legal': {'firstName': 'A', 'lastName': 'B'}}, 'gender': 'female',
                   'matchingCriteria': {'dateOfBirth': '2009-01-02'}}
        if nested:
            payload['matchingCriteria'].update(blocks)
        else:
            payload.update(blocks)
        return payload

    def test_top_level_and_nested_blocks_are_checked(self):
        for nested in (False, True):
            checks = Command().run_checks(self._payload(nested), offline=True)
            names = self._names(checks)
            for expected in ('phone type', 'email type', 'address type', 'email address', 'address region'):
                self.assertIn(expected, names, (nested, expected))
            phone = next(c for c in checks if c.name == 'phone type')
            self.assertFalse(phone.ok)

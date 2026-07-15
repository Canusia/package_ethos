"""Pin the section-registration GUID lookup on SectionDetailMixin."""
from unittest.mock import patch
from django.test import TestCase

try:
    from ethos.ethos.library.ethos import Ethos
except ImportError:
    from ethos.library.ethos import Ethos


class SectionRegistrationIdLookupTests(TestCase):
    def setUp(self):
        self.ethos = Ethos()

    def test_returns_first_record_id(self):
        with patch.object(
            self.ethos, '_get_section_registrations',
            return_value=[{'id': 'REG-GUID-1'}, {'id': 'REG-GUID-2'}],
        ) as m:
            result = self.ethos.get_section_registration_id('STU-GUID', 'SEC-GUID')

        self.assertEqual(result, 'REG-GUID-1')
        m.assert_called_once_with(
            {'registrant': {'id': 'STU-GUID'}, 'section': {'id': 'SEC-GUID'}},
            'section_registration_id',
        )

    def test_returns_none_when_no_records(self):
        with patch.object(self.ethos, '_get_section_registrations', return_value=[]):
            self.assertIsNone(self.ethos.get_section_registration_id('STU', 'SEC'))

    def test_returns_none_when_first_record_has_no_id(self):
        with patch.object(self.ethos, '_get_section_registrations',
                          return_value=[{'noId': True}]):
            self.assertIsNone(self.ethos.get_section_registration_id('STU', 'SEC'))

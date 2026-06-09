import importlib.util

from django.test import SimpleTestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
else:
    from ethos.library.ethos import Ethos


class BuildPersonsCriteriaTests(SimpleTestCase):
    def setUp(self):
        self.b = Ethos().build_persons_criteria

    def test_empty_returns_empty_dict(self):
        self.assertEqual(self.b(), {})

    def test_email_address(self):
        self.assertEqual(self.b(email_address='a@b.com'),
                         {'emails': [{'address': 'a@b.com'}]})

    def test_role(self):
        self.assertEqual(self.b(role='student'),
                         {'roles': [{'role': 'student'}]})

    def test_credentials(self):
        self.assertEqual(
            self.b(credential_type='bannerId', credential_value='B123'),
            {'credentials': [{'type': 'bannerId', 'value': 'B123'}]})

    def test_credential_value_coerced_to_str(self):
        self.assertEqual(
            self.b(credential_type='colleaguePersonId', credential_value=682),
            {'credentials': [{'type': 'colleaguePersonId', 'value': '682'}]})

    def test_alternative_credentials(self):
        self.assertEqual(
            self.b(alt_credential_type_id='TYPE-ID', alt_credential_value='VAL'),
            {'alternativeCredentials': [{'type': {'id': 'TYPE-ID'}, 'value': 'VAL'}]})

    def test_all_name_parts(self):
        self.assertEqual(
            self.b(title='Dr', first_name='Jo', middle_name='Q',
                   last_name_prefix='van', last_name='Doe', pedigree='III'),
            {'names': [{'title': 'Dr', 'firstName': 'Jo', 'middleName': 'Q',
                        'lastNamePrefix': 'van', 'lastName': 'Doe', 'pedigree': 'III'}]})

    def test_partial_name(self):
        self.assertEqual(self.b(first_name='Jo', last_name='Doe'),
                         {'names': [{'firstName': 'Jo', 'lastName': 'Doe'}]})

    def test_combined_filters(self):
        self.assertEqual(
            self.b(last_name='Doe', role='student', email_address='a@b.com'),
            {
                'names': [{'lastName': 'Doe'}],
                'roles': [{'role': 'student'}],
                'emails': [{'address': 'a@b.com'}],
            })

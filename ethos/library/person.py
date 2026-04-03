"""
PersonMixin — person record CRUD, matching, and credentials.
"""

import logging, requests, json

from ..models import EthosLog
from .base import EthosBase

logger = logging.getLogger(__name__)


class PersonMixin(EthosBase):
    """Person-related Ethos operations: create, update, match, lookup."""

    def get_eth_codes(self, student):
        """Return ethnicity GUID codes for a student."""
        guids = self._load_sis_guids()

        codes = student.sis_ethnicity_codes
        ethnicity = []
        for item in guids.get('ethnicities', []):
            if item.get('title') in codes:
                ethnicity.append(
                    item.get('id')
                )

        return ethnicity

    def studentPersonJSON(self, student):
        """Build person JSON payload with demographics, phones, and emails."""
        guids = self._load_sis_guids()

        races = []
        codes = student.sis_race_codes
        for item in guids.get('races', []):
            if item.get('code') in codes:
                races.append(
                    {
                        "race": {
                            "id": item.get('id')
                        }
                    }
                )

        ethnicity = {}
        if student.hispanic:
            ethnicity = {
                "ethnicGroup": {
                    "id": guids.get('hispanic')
                }
            }
        else:
            ethnicity = {
                "ethnicGroup": {
                    "id": guids.get('non_hispanic')
                }
            }

        json_body = {
            "names": [
                {
                    "firstName": student.user.first_name,
                    "fullName": f"{student.user.first_name} {student.user.middle_name} {student.user.last_name}",
                    "lastName": student.user.last_name,
                    "middleName": student.user.middle_name,
                    "preference": "preferred",
                    "type": {
                        "category": "personal"
                    }
                },
                {
                    "fullName": f"{student.user.first_name} {student.user.middle_name} {student.user.last_name}",
                    "type": {
                        "category": "legal"
                    }
                }
            ],
            "addresses": [{
                "address": {
                    "addressLines": [student.user.address1],
                    "place": {
                    "country": {
                        "code": "USA",
                        "locality": student.user.city,
                        "region": {
                        "code": f"US-{student.user.state}"
                        },
                        "postalCode": student.user.postal_code
                    }
                    }
                },
                "type": {
                    "addressType": "home"
                }
            }],
            "countryOfBirth": "USA",
            "races": races,
            "ethnicity": ethnicity,
            "phones": [{
                "type": {
                    "phoneType": "mobile",
                    "detail": {
                        "id": guids.get('phone_type', "e6c932af-3784-4d94-a13b-6bb70b5b1312")
                    }
                },
                "number": f"{student.user.primary_phone.replace('+1 ', '')}"
            }],
            "emails": [
                {
                    "type": {
                        "emailType": "personal",
                        "detail": {
                            "id": guids.get('email_type', "d97179ea-5b29-4679-836c-ddea2f98010e")
                        }
                    },
                    "address": f"{student.user.email}"
                }
            ]
        }

        if student.citizenship_status and student.citizenship_status.lower() != 'unknown':
            json_body["citizenshipStatus"] =  {
                "detail": {
                    "id": guids.get(student.citizenship_status.lower())
                }
            }

        if student.user.secondary_phone:
            json_body['phones'].append({
                "type": {
                    "phoneType": "home",
                    "detail": {
                        "id": guids.get('home_phone_type', "cc64f645-4edc-47f5-94cc-b870028254f8")
                    }
                },
                "number": student.user.secondary_phone.replace('+1 ', '')
            })

        if student.parent_phone:
            json_body['phones'].append({
                "type": {
                    "phoneType": "parent",
                    "detail": {
                        "id": guids.get('parent_phone_type', "a6e5e3a4-90bd-4a77-8e1e-daf2c369aaae")
                    }
                },
                "number": student.parent_phone.replace('+1 ', '')
            })

        if student.parent_email:
            json_body["emails"].append({
                "type": {
                    "emailType": "parent",
                    "detail": {
                        "id": guids.get('parent_email_type', "8436bea7-e2f3-4493-8a33-beb969a0e0bb")
                    }
                },
                "address": f"{student.parent_email}"
            })

        return json.dumps(json_body)

    def studentJSON(self, student):
        """Build student matching JSON payload with SSN and contact info."""
        guids = self._load_sis_guids()

        json_body = {
            'metadata': {
                'createdBy': 'Canusia'
            },
            'id': '00000000-0000-0000-0000-000000000000',
            'names': {
                'legal': {
                    'firstName': f"{student.user.first_name}",
                    'middleName': f"{student.user.middle_name}",
                    'lastName': f"{student.user.last_name}"
                }
            },
            'gender': f"{student.get_gender_code().lower()}",
            'matchingCriteria': {
                'dateOfBirth': f"{student.user.date_of_birth.strftime('%Y-%m-%d')}",
            }
        }

        if student.user.ssn:
            from cis.validators import validate_ssn
            try:
                validate_ssn(student.user.ssn)
                ssn = student.user.ssn.replace('-', '').replace(' ', '')

                if ssn != '000000000':
                    json_body['matchingCriteria']['credential'] = {
                        'type': 'ssn',
                        'value': f"{ssn}"
                    }
            except Exception:
                ...

        json_body['phone'] = {
            'type': {
                'id': guids.get('phone_type', "e6c932af-3784-4d94-a13b-6bb70b5b1312")
            },
            'number': f"{student.user.primary_phone.replace('+1 ', '')}"
        }

        json_body['email'] = {
            'type': {
                'id': guids.get('email_type', "e6c932af-3784-4d94-a13b-6bb70b5b1312")
            },
            'address': f"{student.user.email}"
        }

        json_body['address'] = {
            'type': {
                'id': guids.get('address_type', "e6c932af-3784-4d94-a13b-6bb70b5b1312")
            },
            'addressLines': [
                f"{student.user.address1}"
            ],
            'place': {
                'country': {
                    'code': "USA",
                    'locality': f"{student.user.city}",
                    'region': {
                        'code': f"US-{student.user.state}"
                    },
                    'postalCode': f"{student.user.postal_code}"
                }
            }
        }

        return json.dumps(json_body)

    def studentEmergencyContactJSON(self, student):
        """Build emergency contact JSON payload."""
        from cis.utils import active_term
        guids = self._load_sis_guids()

        json_body = {
            'id': '00000000-0000-0000-0000-000000000000',
            'person': {
                'id': str(student.sis_id)
            },
            'contact': {
                'name': {
                    'fullName': f'{student.parent_first_name} {student.parent_last_name}',
                    'firstName': student.parent_first_name,
                    'lastName': student.parent_last_name
                },
                "types": [
                    {
                        "id": "201b7a67-a74e-4dac-a457-2938b53f2992"
                    }
                ],
                'relationship': {
                    'type': 'Parents'
                }
            }
        }

        if student.parent_phone:
            json_body['contact']['phones'] = [
                    {
                        'number': student.parent_phone.replace('+1 ', '')
                    }
                ]


        return json.dumps(json_body)

    def studentExternalEdJSON(self, student):
        """Build external education JSON payload for high school."""
        from cis.utils import active_term
        guids = self._load_sis_guids()

        json_body = {
            "id": "00000000-0000-0000-0000-000000000000",
            "person": {
                "id": str(student.sis_id)
            },
            "institution": {
                "id": "91c12add-2c8a-48d2-9aef-b6ad8ffb8ee1"
            },
            "attendancePeriods": [{
                "startOn": {
                    "year": 2024,
                    "month": 9,
                    "day": 1
                },
                "endOn": {
                    "year": 2028
                }
            }]
        }

        return json.dumps(json_body)

    def studentMiscJSON(self, student):
        """Build miscellaneous applicant fields JSON payload."""
        json_body = """{
            "miscellaneous1": \"""" + str(student.did_mother_graduate) + """\",
            "miscellaneous2": \"""" + str(student.did_father_graduate) + """\"
        }"""

        return json_body

    def get_bannerid(self, student, **kwargs):
        """Look up a student's Banner ID from their SIS person record."""
        url = self.URL + f'/api/persons/{student.sis_id}'

        resp, sis_log = self._api_request(
            'GET', url, 'get_banner_id',
            description=f'{student} - {student.id}',
            **kwargs
        )
        sis_log.message = {
            'data': f"{student.sis_id}",
            'url': url
        }
        sis_log.save()

        verbose = kwargs.get('verbose', False)

        if resp.ok:
            record = resp.json()

            if verbose:
                print(record)

            banner_id = self._extract_credential(record, 'bannerId')
            if banner_id:
                return (banner_id, sis_log)

        return (
            None,
            sis_log
        )

    def update_person(self, student, **kwargs):
        """Update a person record in Ethos with current student data."""
        url = self.URL + f'/api/persons/{student.sis_id}'

        student_as_json = self.studentPersonJSON(student)

        resp, sis_log = self._api_request(
            'PUT', url, 'person_update',
            data=student_as_json,
            headers={
                "Accept": "application/vnd.hedtech.integration.v12.3.0+json",
                "Content-Type": "application/vnd.hedtech.integration.v12.3.0+json"
            },
            **kwargs
        )

        verbose = kwargs.get('verbose', False)

        if resp.ok:
            record = resp.json()

            if verbose:
                print(record)

            return (
                record.get('id'),
                sis_log
            )

        return (None, sis_log)

    def update_person_ethnicity(self, student, **kwargs):
        """Update a person's ethnicity codes in Ethos."""
        token = self.get_auth_token()

        url = self.URL + f'/api/persons/{student.sis_id}'
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.hedtech.integration.v12.3.0+json",
            "Content-Type": "application/vnd.hedtech.integration.v12.3.0+json"
        }

        verbose = kwargs.get('verbose', False)
        if verbose:
            print(url)

        student_eth_codes = self.get_eth_codes(student)
        if not student_eth_codes:
            return (None, None)

        for code in student_eth_codes:

            student_as_json = {
                "id": str(student.sis_id),
                "names": [
                    {
                        "firstName": student.user.first_name,
                        "fullName": f"{student.user.first_name} {student.user.middle_name} {student.user.last_name}",
                        "lastName": student.user.last_name,
                        "middleName": student.user.middle_name,
                        "preference": "preferred",
                        "type": {
                            "category": "personal"
                        }
                    },
                    {
                        "fullName": f"{student.user.first_name} {student.user.middle_name} {student.user.last_name}",
                        "type": {
                            "category": "legal"
                        }
                    }
                ],
                "ethnicity": {
                    "ethnicGroup": {
                        "id": code
                    }
                }
            }

            student_as_json = json.dumps(student_as_json)
            resp = requests.put(url, headers=headers, data=student_as_json)

            if verbose:
                print(resp.status_code, resp.content)

            log = EthosLog.objects.create(
                method='PUT',
                url=url,
                message_type='person_update_ethnicity',
                request_body=student_as_json,
                response_status=resp.status_code,
                response_body=resp.text,
            )

            if resp.ok:
                record = resp.json()

                if verbose:
                    print(record)

        return (None, log)

    def get_request_status(self, request_id, **kwargs):
        """Check the status of a person matching request."""
        token = self.get_auth_token()

        url = self.URL + f'/api/person-matching-requests/{request_id}'
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.hedtech.integration.v1+json",
            "Content-Type": "application/vnd.hedtech.integration.v1+json",
        }

        verbose = kwargs.get('verbose', False)
        verbose=True
        if verbose:
            print(url)

        resp = requests.get(url, headers=headers)
        if verbose:
            print(resp.status_code, resp.content)

        log = EthosLog.objects.create(
            method='GET',
            url=url,
            message_type='person_request_status',
            response_status=resp.status_code,
            response_body=resp.text,
        )

        if resp.ok:
            record = resp.json()

            if verbose:
                print(record)

            person_id = record.get('person', {}).get('id', None)
            status = record.get('outcomes', [{}])[0].get('status', None)

            return (
                person_id,
                status,
                log
            )

        return (None, None, log)

    def get_or_create_person(self, student, **kwargs):
        """Find or create a person record via person matching."""
        url = self.URL + '/api/person-matching-requests'

        student_as_json = self.studentJSON(student)

        resp, sis_log = self._api_request(
            'POST', url, 'person_get_or_create',
            data=student_as_json,
            headers={
                "Accept": "application/vnd.hedtech.integration.v1+json",
                "Content-Type": "application/vnd.hedtech.integration.person-matching-requests-initiations-prospects.v1+json",
            },
            **kwargs
        )

        verbose = kwargs.get('verbose', False)

        if resp.ok:
            record = resp.json()

            if verbose:
                print(record)

            return (
                record.get('id'),
                record.get('person',{}).get('id'),
                record.get('outcomes',[])[0].get('status'),
                sis_log
            )

        return (
            None,
            None,
            None,
            sis_log
        )

    def create_external_ed(self, student, **kwargs):
        """Create an external education record in Ethos."""
        url = self.URL + '/api/person-external-education'

        student_as_json = self.studentExternalEdJSON(student)

        resp, sis_log = self._api_request(
            'POST', url, 'person_external_education',
            description=f'{student} - {student.id}',
            data=student_as_json,
            headers={
                "Accept": "application/vnd.hedtech.integration.v1+json",
                "Content-Type": "application/vnd.hedtech.integration.v1+json",
            },
            **kwargs
        )

        verbose = kwargs.get('verbose', False)

        if resp.ok:
            record = resp.json()

            if verbose:
                print(record)

            id = record.get('id')
            return (id, sis_log)

        return (None, sis_log)

    def send_emergency_contact(self, student, **kwargs):
        """Create an emergency contact record in Ethos."""
        url = self.URL + '/api/person-emergency-contacts'

        student_as_json = self.studentEmergencyContactJSON(student)

        resp, sis_log = self._api_request(
            'POST', url, 'person_emergency_contact',
            description=f'{student} - {student.id}',
            data=student_as_json,
            headers={
                "Accept": "application/vnd.hedtech.integration.v1+json",
                "Content-Type": "application/vnd.hedtech.integration.v1+json",
            },
            **kwargs
        )

        verbose = kwargs.get('verbose', False)

        if resp.ok:
            record = resp.json()

            if verbose:
                print(record)

            id = record.get('id')
            return (id, sis_log)

        return (None, sis_log)

    def put_misc_info(self, student, **kwargs):
        """Update miscellaneous applicant items in Ethos."""
        url = self.URL + f'/api/applicant-miscellaneous-items/{student.sis_id}'

        student_as_json = self.studentMiscJSON(student)

        resp, sis_log = self._api_request(
            'PUT', url, 'misc_items',
            description=f'{student} - {student.id}',
            data=student_as_json,
            headers={
                "Accept": "application/vnd.hedtech.integration.v1+json",
                "Content-Type": "application/vnd.hedtech.integration.v1+json",
            },
            **kwargs
        )

        verbose = kwargs.get('verbose', False)

        if resp.ok:
            record = resp.json()

            if verbose:
                print(record)

            id = record.get('id')
            return (id, sis_log)

        return (None, sis_log)

    def get_person_id(self, person_create_id, **kwargs):
        """Get a person ID from a find-or-create request."""
        url = self.URL + f"/api/person-find-or-create-requests/{str(person_create_id)}/"

        resp, sis_log = self._api_request(
            'GET', url, 'person_id',
            headers={
                "Content-Type": "application/json"
            },
            **kwargs
        )

        verbose = kwargs.get('verbose', False)

        if resp.ok:
            record = resp.json()

            if verbose:
                print(record)

            return {
                'id': record.get('id'),
                'status': record.get('status'),
                'personid': record.get('personId')
            }

        return {
            'id': None,
            'status': None,
            'personid': None
        }

    def get_person(self, personid, **kwargs):
        """Retrieve a person record by ID, extracting Banner ID and email."""
        url = self.URL + f'/api/persons/{str(personid)}'

        resp, sis_log = self._api_request(
            'GET', url, 'get_person',
            description=f"{personid}",
            **kwargs
        )

        verbose = kwargs.get('verbose', False)

        if resp.ok:
            record = resp.json()

            if verbose:
                print(record)

            bannerid = self._extract_credential(record, 'bannerId')

            other_email = None
            try:
                emails = record.get('emails')
                if emails:
                    for e in emails:
                        if e.get('type').get('emailType') == 'personal':
                            other_email = e.get('address', '').replace('#', '')
                            break
            except Exception:
                other_email = None

            return {
                'bannerid': bannerid,
                'other_email': other_email,
            }
        return None

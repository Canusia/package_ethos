"""
RegistrationMixin — section registrations, holds, and mirroring.
"""

import logging, requests, json, datetime

from cis.models.sis import SIS_Log
from .base import EthosBase

logger = logging.getLogger(__name__)


class RegistrationMixin(EthosBase):
    """Registration operations: holds, status updates, mirroring."""

    def sendRegistrationHold(self, registration):
        """Submit a financial registration hold to Ethos."""
        json_payload = self.registrationHoldJSON(registration)

        url = self.URL + '/api/person-holds'
        resp, sis_log = self._api_request(
            'POST', url, 'registration_hold',
            description=f"{registration.student} / {registration}",
            data=json_payload,
            headers={
                "Content-Type": "application/vnd.hedtech.integration.v6+json"
            }
        )

        if resp.ok:
            record = resp.json()
            return (record, sis_log)

        return (None, sis_log)

    def registrationHoldJSON(self, registration):
        """Build registration hold JSON payload."""
        from cis.utils import active_term
        import datetime
        guids = self._load_sis_guids()

        financial_hold_id = guids.get('financial_hold', "5b93334c-4cad-4451-b925-962a35cdff5c")

        reason = ""
        if registration.pay_type == 'school_pay':
            reason = f"Canusia {registration.student.highschool.sau} ${registration.class_section.student_cost}"
        elif registration.pay_type == 'school_partial':
            reason = f"Canusia {registration.student.highschool.sau} ${registration.non_student_pay_amount}"

        json_body = {
            "id": "00000000-0000-0000-0000-000000000000",
            "person": {
                "id": str(registration.student.sis_id)
            },
            "reason": reason,
            "startOn": datetime.datetime.now().strftime('%Y-%m-%d') + "T00:00:00Z",
            "endOn": "2099-12-31T00:00:00Z",
            "type": {
                "category": "financial",
                "detail": {
                    "id": financial_hold_id
                }
            }
        }

        return json.dumps(json_body)

    def update_registration_status(self, registration_response, status, section_number):
        """Update a section registration status in Ethos."""
        token = self.get_auth_token()
        json_data = registration_response

        registration_id = registration_response.get('id')
        old_status = registration_response['stcStatuses'][0]

        json_data = {}
        stcStatus = "GS"

        if status == 'registered':
            if str(section_number).startswith == 'L':
                if old_status['stcStatus'] == 'N':
                    stcStatus = "L"
                if old_status['stcStatus'] == 'A':
                    stcStatus = "LA"
            else:
                if old_status['stcStatus'] == 'N':
                    stcStatus = "GS"
                if old_status['stcStatus'] == 'A':
                    stcStatus = "GA"

        if status == 'dropped':
            if old_status['stcStatus'] == 'D':
                    stcStatus = "LD"

        json_data['id'] = registration_id
        json_data['stcStatuses'] =  [{
            "stcStatus": stcStatus,
            "stcStatusDate": datetime.datetime.now().strftime('%Y-%m-%d'),
            "stcStatusTime": datetime.datetime.now().strftime('%H:%M:%S'),
        }]

        json_data['stcStatuses'].append(
            old_status
        )

        url = self.URL + '/api/section-registrations/' + registration_id

        headers = {
            "Authorization": f"Bearer {token}",
            'Accept': 'application/vnd.hedtech.integration.v16+json',
            'Content-Type': 'application/vnd.hedtech.integration.v16+json'
        }

        sis_log = SIS_Log()
        sis_log.message_type = 'registration_status'
        sis_log.message = {
            'data': json_data,
            'url': url
        }

        resp = requests.put(
            url,
            headers=headers,
            json=json_data
        )

        sis_log.response = {
            'status': resp.status_code,
            'response': resp.text
        }

        sis_log.save()

        if resp.ok:
            return (True, sis_log)

        return (False, sis_log)

    def update_registration(self, student_sis_id, section_id, status, registration_id):
        """Update a section registration record in Ethos."""
        token = self.get_auth_token()

        url = self.URL + '/api/section-registrations/' + str(registration_id)
        headers = {
            "Authorization": f"Bearer {token}",
            'Accept': 'application/vnd.hedtech.integration.v16+json',
            'Content-Type': 'application/vnd.hedtech.integration.v16+json'
        }

        json_data = {
            "id": str(registration_id),
            "registrant": {
                "id": str(student_sis_id)
            },
            "section": {
                "id": str(section_id)
            },
            "academicLevel": {
                "id": "290e319e-93c6-4421-beab-3ff219b5a0d5"
            },
            "status": {
                "registrationStatus": "notRegistered",
                "sectionRegistrationStatusReason": status
            },
            "statusDate": datetime.datetime.now().strftime("%Y-%m-%d")
        }

        sis_log = SIS_Log()
        sis_log.message_type = f'class_{status}'
        sis_log.message = {
            'data': json_data,
            'url': url
        }

        resp = requests.put(
            url,
            headers=headers,
            json=json_data
        )

        sis_log.response = {
            'status': resp.status_code,
            'response': resp.text
        }

        sis_log.save()

        if resp.ok:
            return (True, sis_log)
        return (False, sis_log)

    def mirror_linked_registrations(self, student_banner_id, term_code, crns):
        """Register multiple linked CRNs together via registration-register."""
        token = self.get_auth_token()

        url = self.URL + '/api/registration-register'
        headers = {
            "Authorization": f"Bearer {token}",
        }

        json_data = {
            "bannerId": f"{student_banner_id}",
            "term": f"{term_code}",
            "systemIn": "SB",
            "conditionalAddDrop": "N",
            "courseReferenceNumbers": []
        }

        for crn in crns:
            json_data['courseReferenceNumbers'].append({
                "courseReferenceNumber": f"{crn}",
                "courseRegistrationStatus": "RW"
            })

        sis_log = SIS_Log()
        sis_log.message_type = f'linked_class_register'
        sis_log.message = {
            'data': json_data,
            'url': url
        }

        resp = requests.post(
            url,
            headers=headers,
            json=json_data
        )

        if resp.ok:
            sis_log.response = {
                'status': resp.status_code,
                'message': resp.text
            }
            sis_log.save()

            try:
                for r in resp.json()['registrations']:
                    if r.get('failureReasons'):
                        return (False, sis_log, None, None)
                    if r.get('statusIndicator') == 'F':
                        return (False, sis_log, None, None)
            except Exception:
                ...

            if resp.json().get('failedRegistrations') :
                return (False, sis_log, None, None)

            return (True, sis_log, None, 'registered')

        sis_log.response = {
            'status': resp.status_code,
            'message': resp.text
        }
        sis_log.save()
        return (False, sis_log, None, None)

    def mirror_registration(self, student_sis_id, section_id, status, registration_id=None, section_number=None):
        """Create or update a section registration in Ethos."""
        if registration_id:
            return self.update_registration(
                student_sis_id,
                section_id,
                status,
                registration_id
            )

        token = self.get_auth_token()

        url = self.URL + '/api/section-registrations'
        headers = {
            "Authorization": f"Bearer {token}",
            'Accept': 'application/vnd.hedtech.integration.v16+json',
            'Content-Type': 'application/vnd.hedtech.integration.v16+json'
        }

        json_body = {
            "id":"00000000-0000-0000-0000-000000000000",
            "registrant": {
                "id": student_sis_id
            },
            "section": {
                "id": section_id
            },
            "academicLevel": {
                "id": "8ae4bf82-85ce-444f-a9e4-43e65b53829a"
            },
            "status": {
                "registrationStatus": status,
                "sectionRegistrationStatusReason": status
            },
            "statusDate": datetime.datetime.now().strftime("%Y-%m-%d")
        }

        sis_log = SIS_Log()
        sis_log.message_type = f'class_{status}'
        sis_log.message = {
            'data': json_body,
            'url': url
        }

        resp = requests.post(
            url,
            headers=headers,
            json=json_body
        )

        sis_log.response = {
            'status': resp.status_code,
            'response': resp.text
        }

        sis_log.save()

        if resp.ok:
            try:
                registration_sis_id = resp.json().get('id')
                registration_status = resp.json().get('status', {}).get('registrationStatus')
            except Exception:
                registration_sis_id = None
                registration_status = None

            return (True, sis_log, registration_sis_id, registration_status)

        return (False, sis_log, None, None)

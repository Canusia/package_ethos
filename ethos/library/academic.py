"""
AcademicMixin — academic programs, admissions, and reference data.
"""

import logging
import requests
import json
import datetime

from urllib.parse import urljoin, urlencode

from .base import EthosBase

logger = logging.getLogger(__name__)


class AcademicMixin(EthosBase):
    """Academic operations: programs, admissions, courses, sites."""

    def studentAdmissionJSON(self, student):
        """Build admission application JSON payload."""
        from cis.utils import active_term
        guids = self._load_sis_guids()

        admission_population = guids.get('admission_population', "cf342721-190a-4f48-8b95-c2f9cd65725f")

        academic_period = self.get_academic_period_id(active_term().code)
        student_type = guids.get('student_type', {}).get('id', '904c5eb0-5b0f-4db8-ba7c-133a94f20a54')
        residency_type = guids.get('residency_type', {}).get('id', 'a57dedba-4d00-4e2a-b453-9de372b17300')
        program = guids.get('program', {}).get('id', '2cc795f1-d6c3-441f-bb0f-b6d2e1411ff4')
        academic_level = guids.get('academic_level', {}).get('id', '8ae4bf82-85ce-444f-a9e4-43e65b53829a')

        json_body = {
            'id': '00000000-0000-0000-0000-000000000000',
            'applicant': {
                'id': str(student.sis_id)
            },
            'admissionPopulation': {
                'id': str(admission_population)
            },
            'academicPeriod': {
                'id': str(academic_period)
            },
            'type': {
                'id': str(student_type)
            },
            'residencyType': {
                'id': str(residency_type)
            },
            "applicationAcademicPrograms": [{
               "program": {
                   "id": str(program)
               },
               "academicLevel": {
                   "id": str(academic_level)
               }
           }]
        }

        return json.dumps(json_body)

    def studentAdmissionDecisionJSON(self, student):
        """Build admission decision JSON payload."""        
        guids = self._load_sis_guids()

        decision_type = guids.get('decision_type', "83243414-b2d7-48a0-8ce4-7847103fc0e0")

        json_body = {
            'id': '00000000-0000-0000-0000-000000000000',
            'application': {
                'id': str(student.admission_id)
            },
            'decisionType': {
                'id': str(decision_type)
            },
            'decidedOn': datetime.datetime.now().strftime('%Y-%m-%d') + "T00:00:01.916Z"
        }

        return json.dumps(json_body)

    def studentAcademicProgramJSON(self, student):
        """Build academic program JSON payload with catalog year."""
        guids = self._load_sis_guids()

        year = student.user.created_at.strftime('%Y')
        catalog = guids.get('catalog',{}).get(str(year))

        json_body = """{
            "id": "00000000-0000-0000-0000-000000000000",
            "student": {
                "id": \"""" + str(student.sis_id) + """\"
            },
            "catalog": {
                "id": \"""" + str(catalog) + """\"
            }
        }"""

        return json_body

    def get_educational_institution_id(self, highschool):
        """Look up an educational institution GUID by colleague ID."""
        base_url = self.URL  # Make sure this ends with a slash or use urljoin
        endpoint = 'api/educational-institutions'
        criteria = {
            "credentials": [
                {
                    "type": "colleaguePersonId",
                    "value": highschool.colleague_id
                }
            ]
        }

        query_params = {
            "criteria": json.dumps(criteria)
        }

        url = urljoin(base_url, endpoint) + '?' + urlencode(query_params)

        resp, sis_log = self._api_request('GET', url, 'ed_insitution_id')

        if resp.ok:
            result = resp.json()
            return str(result[0].get('id'))

        return None

    def get_academic_programs(self, code=None):
        """List academic programs, optionally filtered by code."""
        token = self.get_auth_token()

        if not code:
            url = self.URL + '/api/academic-programs'

        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.get(url, headers=headers)

        if resp.ok:
            acad_periods = resp.json()

            codes = []
            if not code:
                codes.append("[")
                for acad_period in acad_periods:
                    codes.append("{" + f"\"{acad_period.get('title')}\": \"{acad_period.get('id')}\"" + "},")
                codes.append("]")

                return codes

            if acad_periods[0]:
                return acad_periods[0].get('id')

            return None
        return None

    def submit_academic_program(self, student, **kwargs):
        """Submit a student academic program to Ethos."""
        url = self.URL + '/api/student-academic-programs'

        student_as_json = self.studentAcademicProgramJSON(student)

        resp, sis_log = self._api_request(
            'POST', url, 'academic_program',
            data=student_as_json,
            headers={
                "Accept": "application/vnd.hedtech.integration.v17+json",
                "Content-Type": "application/vnd.hedtech.integration.student-academic-programs-submissions.v1+json",
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

    def create_admission_application(self, student, **kwargs):
        """Create an admission application in Ethos."""
        url = self.URL + '/api/admission-applications'

        student_as_json = self.studentAdmissionJSON(student)

        resp, sis_log = self._api_request(
            'POST', url, 'admission_application',
            data=student_as_json,
            headers={
                "Accept": "application/vnd.hedtech.integration.v16+json",
                "Content-Type": "application/vnd.hedtech.integration.admission-applications-submissions.v1+json",
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

    def accept_admission_decision(self, student, **kwargs):
        """Submit an admission decision to Ethos."""
        url = self.URL + '/api/admission-decisions'

        body = self.studentAdmissionDecisionJSON(student)

        verbose = kwargs.get('verbose', False)
        if verbose:
            print(url)
            print(body)

        resp, sis_log = self._api_request(
            'POST', url, 'admission_decision',
            data=body,
            headers={
                "Accept": "application/vnd.hedtech.integration.v11+json",
                "Content-Type": "application/vnd.hedtech.integration.v11+json",
            },
            **kwargs
        )

        if resp.ok:
            record = resp.json()

            if verbose:
                print(record)

            id = record.get('id')
            return (id, sis_log)
        return (None, sis_log)

    def get_sites(self, **kwargs):
        """List available sites from Ethos."""
        url = self.URL + f"/api/sites"

        resp, sis_log = self._api_request(
            'GET', url, 'sites',
            headers={
                "Content-Type": "application/json"
            },
            **kwargs
        )

        verbose = kwargs.get('verbose', False)

        if resp.ok:
            records = resp.json()

            if verbose:
                print(records)

            return records

        return None

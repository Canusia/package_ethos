"""
PaymentMixin — payments, fees, and FRL exemptions.
"""

import logging, json, datetime

from .base import EthosBase

logger = logging.getLogger(__name__)


class PaymentMixin(EthosBase):
    """Payment operations: fee assessment, FRL exemptions, student payments."""

    def assess_fee(self, student, term_code=None, **kwargs):
        """Submit a registration fee assessment to Ethos."""
        from cis.utils import active_term

        data = {
            'bannerId': student.user.psid,
            'term': term_code or active_term().code
        }

        url = self.URL + '/api/registration-fee-assessment'
        resp, sis_log = self._api_request(
            'POST', url, 'fee_assessment',
            description=f"{student}",
            json_data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/vnd.hedtech.v1+json"
            },
            **kwargs
        )

        verbose = kwargs.get('verbose', False)

        if resp.ok:
            record = resp.json()

            if verbose:
                print(record)

            return (record, sis_log)
        return (None, sis_log)

    def sendStudentFRL(self, student_registration):
        """Submit a free/reduced lunch payment exemption to Ethos."""
        student = student_registration.student

        json_payload = self.studentFRLJSON(student_registration)

        url = self.URL + '/api/student-payments'
        resp, sis_log = self._api_request(
            'POST', url, 'student_frl',
            description=f"{student} / {student_registration}",
            data=json_payload,
            headers={
                "Content-Type": "application/vnd.hedtech.integration.v16+json",
                "Accept": "application/vnd.hedtech.integration.v16+json"
            }
        )

        if resp.ok:
            record = resp.json()
            return (record, sis_log)
        return (None, sis_log)

    def studentFRLJSON(self, student_registration):
        """Build FRL payment exemption JSON payload."""
        student = student_registration.student

        from cis.utils import active_term
        guids = self._load_sis_guids()

        academic_period = self.get_academic_period_id(active_term().code)
        funding_destination = guids.get('funding_destination', "da3c7e6a-f33e-4174-b74b-e561ab684c25")
        funding_source = guids.get('funding_source', "da3c7e6a-f33e-4174-b74b-e561ab684c25")
        override_description = guids.get('override_description', "Dual Credit High School Waiver")

        # if time is greater than 7pm then date is next day
        paid_on = datetime.datetime.now()

        json_body = {
            'id': '00000000-0000-0000-0000-000000000000',
            'student': {
                'id': str(student.sis_id)
            },
            'academicPeriod': {
                'id': str(academic_period)
            },
            'fundingSource': {
                'id': str(funding_source)
            },
            'fundingDestination': {
                'id': str(funding_destination)
            },
            'overrideDescription': str(override_description),
            "paymentType": "exemption",
            "paidOn": paid_on.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'amount': {
                'currency': 'USD',
                'value': float(student_registration.class_section.student_cost)
            }
        }

        return json.dumps(json_body)

    def sendStudentPayment(self, transaction):
        """Submit a student payment to Ethos."""
        student = transaction.student

        json_payload = self.studentPaymentJSON(transaction)

        url = self.URL + '/api/student-payments'
        resp, sis_log = self._api_request(
            'POST', url, 'student_payment',
            description=f"{student} / {transaction}",
            data=json_payload,
            headers={
                "Content-Type": "application/vnd.hedtech.integration.v16+json",
                "Accept": "application/vnd.hedtech.integration.v16+json"
            }
        )

        if resp.ok:
            record = resp.json()
            return (record, sis_log)
        return (None, sis_log)

    def studentPaymentJSON(self, transaction):
        """Build student payment JSON payload."""
        student = transaction.student

        from cis.utils import active_term
        guids = self._load_sis_guids()

        academic_period = self.get_academic_period_id(transaction.term.code)
        funding_destination = guids.get('payment_funding_destination', "4f5d6030-f28b-4fc5-9d3c-9e067ea2a88f")
        funding_source = guids.get('payment_funding_source', "4f5d6030-f28b-4fc5-9d3c-9e067ea2a88f")

        if 'ACH Payment' in transaction.description:
            funding_destination = guids.get('ach_funding_destination', "3ef891f3-e589-4d54-97f7-b6265548ff2f")
            funding_source = guids.get('ach_funding_source', "3ef891f3-e589-4d54-97f7-b6265548ff2f")

        override_description = guids.get('override_description', "Student Payment")

        # if time is greater than 7pm then date is next day
        paid_on = datetime.datetime.now()
        json_body = {
            'id': '00000000-0000-0000-0000-000000000000',
            'student': {
                'id': str(student.sis_id)
            },
            'academicPeriod': {
                'id': str(academic_period)
            },
            'fundingSource': {
                'id': str(funding_source)
            },
            'fundingDestination': {
                'id': str(funding_destination)
            },
            "paymentType": "cash",
            "paidOn": paid_on.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'amount': {
                'currency': 'USD',
                'value': float(transaction.amount)
            }
        }

        return json.dumps(json_body)

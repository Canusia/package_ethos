"""
SectionMixin — section fetching, formatting, and message consumption.
"""

import logging, json, datetime

from urllib.parse import urlencode

from .base import EthosBase

logger = logging.getLogger(__name__)


class SectionMixin(EthosBase):
    """Section operations: fetch, format, and consume messages."""

    def get_messages(self, limit=10):
        """Consume messages from the Ethos message queue."""
        token = self.get_auth_token()

        if not limit:
            url = self.URL + '/consume'
        else:
            url = self.URL + f'/consume?limit={limit}'
        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.get(url, headers=headers)

        if resp.ok:
            return resp.json()
        return None


    def get_class_section_guid(self, class_section):
        """This needs to be refactored"""

        # token = self.get_auth_token()

        # acad_period_id = self.get_academic_period_id(class_section.term.code)

        # url = self.URL + '/api/sections?criteria={"academicPeriod":{"id":"' + acad_period_id + '"},"code":"' + class_section.class_number + '"}'

        # headers = {"Authorization": f"Bearer {token}"}


        # sis_log = SIS_Log()
        # sis_log.message_type = f'get_class_guid'
        # sis_log.message = {
        #     'data': {
        #         'code': class_section.class_number,
        #         'academic_period_id': acad_period_id
        #     },
        #     'url': url
        # }
        # sis_log.save()
        # resp = requests.get(url, headers=headers)


        # sis_log.response = {
        #     'status': resp.status_code,
        #     'response': resp.text
        # }

        # sis_log.save()

        # if resp.ok:
        #     response = resp.json()
        #     if response:
        #         return response[0].get('id')
        #     else:
        #         return None
        return None
    
    def format_sections(self, raw_sections):
        """Transform raw Ethos section data into formatted dictionaries."""
        sections = []

        for section in raw_sections:
            class_number = section['code']
            sis_id = section['id']

            subject_name = section['course']['subject']['abbreviation']
            catalog_number = section['course']['number']
            course_name = subject_name + ' ' + catalog_number

            section_number = section['number']
            title = section['course']['titles'][0]['value']

            start_date = section['startOn']
            end_date = section['endOn']

            term_code = section['academicPeriod']['code']
            status = section['status']['category']

            max_enrollment = section.get('maxEnrollment', 0)
            course_type = None

            site_code, site_title = None, None
            if section.get('site'):
                site_code = section['site']['code']
                site_title = section['site']['title']

            max_seats, available_seats = -1, -1

            try:
                roster = section.get('instructorRosterDetails', [])
                primary = next(
                    (r for r in roster if r.get('instructorRole') == 'primary'),
                    roster[0] if roster else None
                )
                if primary:
                    faculty_first_name = primary['instructor']['names'][0]['firstName']
                    faculty_last_name = primary['instructor']['names'][0]['lastName']
                    faculty_sis_id = primary['instructor']['detail']['id']
                    faculty_id, faculty_email = '', ''
                    for k in primary['instructor'].get('credentials', []):
                        if k['type'] == 'bannerId':
                            faculty_id = k['value']
                        elif k['type'] == 'bannerUserName':
                            faculty_email = k['value'] + '@ewu.edu'
                else:
                    faculty_first_name, faculty_last_name, faculty_id, faculty_email, faculty_sis_id = '', '', '', '', ''
            except Exception:
                faculty_first_name, faculty_last_name, faculty_id, faculty_email, faculty_sis_id = '', '', '', '', ''

            days = ''
            try:
                instructional_events = section['instructionalEvents'][0]
                location_code = instructional_events['locations'][0]['location']['building']['code']
            except Exception:
                location_code = None

            try:
                instruction_mode = instructional_events['instructionalMethod']['title']
            except Exception:
                instruction_mode = ''

            try:
                start_time = datetime.datetime.fromisoformat(
                    instructional_events['recurrence']['timePeriod']['startOn']
                ).strftime('%H%M')

                end_time = datetime.datetime.fromisoformat(
                    instructional_events['recurrence']['timePeriod']['endOn']
                ).strftime('%H%M')
            except Exception:
                start_time = 0
                end_time = 2359

            try:
                if instructional_events['recurrence']['repeatRule']['daysOfWeek']:
                    days = ','.join(instructional_events['recurrence']['repeatRule']['daysOfWeek'])
            except Exception:
                days = ''

            credits = 99

            sections.append(
                {
                    'id': sis_id,
                    'title': title,
                    'subject_name': subject_name,
                    'class_number': class_number,
                    'course_name': course_name,
                    'catalog_number': catalog_number,
                    'section_number': section_number,
                    'start_date': start_date,
                    'end_date': end_date,
                    'status': status,
                    'location_code': site_code,
                    'location_title': site_title,
                    'instruction_mode': instruction_mode,
                    'days': days,
                    'start_time': start_time,
                    'end_time': end_time,
                    'instructor': {
                        'first_name': faculty_first_name,
                        'last_name': faculty_last_name,
                        'email': faculty_email,
                        'id': faculty_id,
                        'sis_id': faculty_sis_id
                    },
                    'credit_hours': credits,
                    'max_enrollment': max_enrollment,
                    'site_code': site_code,
                    'meta': section
                }
            )

        return sections

    def get_sections(self, term_code=None, return_type='formatted', period_id=None, **kwargs):
        """Fetch all sections for a term with pagination.

        Args:
            term_code: Academic period code to filter by (looked up to get period_id).
            return_type: 'formatted' runs format_sections, 'raw' returns API data as-is.
            period_id: Academic period GUID. If provided, skips the term_code lookup.
            **kwargs: Passed to _api_request (e.g. verbose=True).

        Returns:
            List of section dicts (formatted or raw).
        """
        if period_id is None:
            period_id = self.get_academic_period_id(term_code)

        criteria = {'academicPeriod': { 'detail': {'id': period_id}}}
        
        query = urlencode({'criteria': json.dumps(criteria)})
        base_url = f'{self.URL}/api/sections?{query}'

        all_sections = []
        offset = 0

        while True:
            url = f'{base_url}&offset={offset}'

            logger.info(f'Fetching: {url}')

            resp, sis_log = self._api_request(
                'GET', url, 'sections',
                headers={
                    'Accept': 'application/vnd.hedtech.integration.sections-maximum.v16+json',
                },
                **kwargs,
            )

            if not resp.ok:
                logger.error(f'Failed to fetch sections for {term_code or period_id}: {resp.status_code} {resp.text}')
                break

            records = resp.json()
            all_sections.extend(records)

            total_count = resp.headers.get('x-total-count')
            page_size = int(resp.headers.get('x-max-page-size', 500))

            logger.info(f'Retrieved {len(records)} records (total so far: {len(all_sections)}, x-total-count: {total_count})')

            if total_count is not None:
                if len(all_sections) >= int(total_count):
                    break

            if len(records) < page_size:
                break

            offset += len(records)

        logger.info(f'Done. Total sections fetched: {len(all_sections)}')

        if return_type == 'formatted':
            return self.format_sections(all_sections)

        return all_sections

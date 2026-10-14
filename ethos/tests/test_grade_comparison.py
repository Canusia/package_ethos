"""Banner vs MyCE Grades: Banner reads, row comparison, the report's CSV."""
import csv
import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase

from cis.models.course import Cohort, Course
from cis.models.highschool import HighSchool
from cis.models.section import ClassSection, StudentRegistration
from cis.models.student import Student
from cis.models.teacher import Teacher
from cis.models.term import AcademicYear, Term

from .. import grade_comparison as gc
from .. import grade_push
from ..reports import banner_grade_comparison as report_mod

SECTION = '7ef5c6f6-4ac6-431b-91f7-c555812802d8'
FINAL = 'f70332ec-52b3-461b-808f-903ad1aa1883'
REG1 = '91135eda-bb22-4617-9a22-8d38f0b4c67c'
REG2 = '22222222-bb22-4617-9a22-8d38f0b4c67c'
REG3 = '33333333-bb22-4617-9a22-8d38f0b4c67c'
PERSON = 'ab813820-a21f-4d76-932a-97df40882b1c'
RECORD = '4a675f01-0000-4000-8000-000000000000'
REGISTERED = {'registered', 'enrolled'}


def _resp(status, body):
    r = MagicMock(ok=200 <= status < 300, status_code=status)
    r.json.return_value = body
    return r


def _client(routes):
    """Fake Ethos client; `routes` maps a URL fragment to (status, body) or a list of them."""
    client = MagicMock(URL='https://ethos')
    client._load_sis_guids.return_value = {'final_grade_type': {'id': FINAL}}
    calls = client.calls = []

    def api(method, url, message_type, **kwargs):
        calls.append(url)
        for fragment, answer in routes.items():
            if fragment in url:
                if isinstance(answer, list):
                    answer = answer.pop(0)
                return _resp(*answer), MagicMock(pk=7)
        raise AssertionError(f'unexpected url {url}')
    client._api_request.side_effect = api
    return client


def _banner_reg(reg_id, status='registered', reason='registered', person=PERSON):
    return {'id': reg_id, 'registrant': {'id': person}, 'section': {'id': SECTION},
            'status': {'registrationStatus': status, 'sectionRegistrationStatusReason': reason}}


def _banner_grade(reg_id, letter):
    return {'id': RECORD, 'sectionRegistration': {'id': reg_id},
            'details': {'grades': [{'grade': {'id': 'g', 'value': letter},
                                    'type': {'id': FINAL, 'code': 'FINAL'}}]}}


def _registration(sis_id, status='registered', grade='A'):
    user = SimpleNamespace(first_name='Amy', last_name='Young', psid='100', email='a@x.org')
    section = SimpleNamespace(
        course=SimpleNamespace(name='ENGL 101', title='Composition'),
        term=SimpleNamespace(code='202610', label='Fall 2026'),
        teacher=SimpleNamespace(user=SimpleNamespace(first_name='Brock', last_name='Anderson')),
        class_number='12345', section_number='01', grade_status='submitted')
    return SimpleNamespace(
        id=1, sis_id=sis_id, status=status, grade=grade, class_section=section,
        student=SimpleNamespace(user=user), highschool=SimpleNamespace(name='HS'),
        get_status_display=lambda: status.title())


class BannerReadTests(SimpleTestCase):
    def test_section_reads_registrations_and_grades_by_class(self):
        client = _client({
            'section-registrations?': (200, [_banner_reg(REG1)]),
            'student-unverified-grades?': (200, [_banner_grade(REG1, 'B')]),
        })
        regs, grades = gc.banner_section(client, SECTION, FINAL)
        self.assertEqual(regs[REG1]['status'], 'registered')
        self.assertEqual(grades[REG1], ('B', 'FINAL', RECORD))
        grade_url = [u for u in client.calls if 'unverified' in u][0]
        self.assertIn('section=', grade_url)          # named query, not criteria
        self.assertNotIn('criteria=', grade_url)

    def test_pages_until_a_short_page(self):
        with patch.object(gc, 'PAGE_SIZE', 2):
            client = _client({
                'section-registrations?': [
                    (200, [_banner_reg(REG1), _banner_reg(REG2)]),
                    (200, [_banner_reg(REG3)])],
                'student-unverified-grades?': (200, []),
            })
            regs, _ = gc.banner_section(client, SECTION, FINAL)
        self.assertEqual(set(regs), {REG1, REG2, REG3})
        self.assertIn('offset=2', [u for u in client.calls if 'registrations' in u][1])

    def test_single_registration_404_is_missing_not_an_error(self):
        client = _client({f'section-registrations/{REG1}': (404, {})})
        self.assertEqual(gc.banner_registration(client, REG1, FINAL), (None, None))


class CompareRegistrationTests(SimpleTestCase):
    def _row(self, reg, banner_reg=None, grade=None, last_sent=None):
        return gc.compare_registration(reg, banner_reg, grade, REGISTERED, last_sent)

    def test_match(self):
        row = self._row(_registration(REG1), gc._registration_row(_banner_reg(REG1)),
                        ('A', 'FINAL', RECORD))
        self.assertEqual(row['Result'], gc.MATCH)
        self.assertEqual((row['Status Match'], row['Grade Match']), ('Y', 'Y'))
        self.assertEqual(row['CRN'], '12345')
        self.assertEqual(row['Section Grade Status'], 'Submitted')

    def test_grade_differs(self):
        row = self._row(_registration(REG1), gc._registration_row(_banner_reg(REG1)),
                        ('B', 'FINAL', RECORD))
        self.assertEqual(row['Result'], gc.GRADE_DIFFERS)

    def test_grade_missing_in_banner_and_only_in_banner(self):
        banner_reg = gc._registration_row(_banner_reg(REG1))
        self.assertEqual(self._row(_registration(REG1), banner_reg)['Result'],
                         gc.GRADE_MISSING_IN_BANNER)
        self.assertEqual(self._row(_registration(REG1, grade='-'), banner_reg,
                                   ('C', 'FINAL', RECORD))['Result'], gc.GRADE_ONLY_IN_BANNER)

    def test_no_grade_anywhere_is_a_match(self):
        row = self._row(_registration(REG1, grade=''), gc._registration_row(_banner_reg(REG1)))
        self.assertEqual(row['Result'], gc.MATCH)

    def test_status_differs_alone_and_with_grade(self):
        dropped = gc._registration_row(_banner_reg(REG1, 'notRegistered', 'dropped'))
        self.assertEqual(self._row(_registration(REG1), dropped, ('A', 'FINAL', RECORD))['Result'],
                         gc.STATUS_DIFFERS)
        self.assertEqual(self._row(_registration(REG1), dropped, ('B', 'FINAL', RECORD))['Result'],
                         f'{gc.GRADE_DIFFERS}; {gc.STATUS_DIFFERS}')

    def test_dropped_in_both_matches(self):
        row = self._row(_registration(REG1, status='dropped', grade=''),
                        gc._registration_row(_banner_reg(REG1, 'notRegistered', 'dropped')))
        self.assertEqual(row['Result'], gc.MATCH)

    def test_missing_in_banner_and_no_registration_id(self):
        self.assertEqual(self._row(_registration(REG1))['Result'], gc.MISSING_IN_BANNER)
        self.assertEqual(self._row(_registration(None))['Result'], gc.NO_REGISTRATION_ID)

    def test_last_sent_is_formatted(self):
        import datetime
        row = self._row(_registration(None), last_sent=datetime.datetime(2026, 10, 14, 15, 5))
        self.assertEqual(row['Last Sent'], '10/14/2026 03:05 PM')


class CompareSectionTests(SimpleTestCase):
    def _section(self, sis_id=SECTION):
        reg = _registration(REG1)
        section = reg.class_section
        section.sis_id = sis_id
        return section, reg

    def test_banner_only_rows_skip_registrations_filtered_out_of_myce(self):
        section, reg = self._section()
        client = _client({
            'section-registrations?': (200, [_banner_reg(REG1), _banner_reg(REG2),
                                             _banner_reg(REG3)]),
            'student-unverified-grades?': (200, []),
            f'persons/{PERSON}': (200, {'names': [{'fullName': 'Banner Person',
                                                    'preference': 'preferred'}]}),
        })
        rows = gc.compare_section(
            client, section, [reg], {REG1, REG2}, final_type_id=FINAL,
            include_banner_only=True, registered=REGISTERED, last_sent={}, names={})
        results = [(r['Result'], r['Banner Section Registration ID']) for r in rows]
        self.assertEqual(results, [(gc.GRADE_MISSING_IN_BANNER, REG1), (gc.ONLY_IN_BANNER, REG3)])
        self.assertEqual(rows[1]['Student'], 'Banner Person')

    def test_banner_only_can_be_left_out(self):
        section, reg = self._section()
        client = _client({'section-registrations?': (200, [_banner_reg(REG3)]),
                          'student-unverified-grades?': (200, [])})
        rows = gc.compare_section(
            client, section, [reg], {REG1}, final_type_id=FINAL,
            include_banner_only=False, registered=REGISTERED, last_sent={}, names={})
        self.assertEqual([r['Result'] for r in rows], [gc.MISSING_IN_BANNER])

    def test_class_without_section_guid_falls_back_per_registration(self):
        section, reg = self._section(sis_id=None)
        client = _client({
            f'section-registrations/{REG1}': (200, _banner_reg(REG1)),
            'student-unverified-grades?': (200, [_banner_grade(REG1, 'A')]),
        })
        rows = gc.compare_section(
            client, section, [reg], {REG1}, final_type_id=FINAL,
            include_banner_only=True, registered=REGISTERED, last_sent={}, names={})
        self.assertEqual([r['Result'] for r in rows], [gc.MATCH])

    def test_banner_failure_marks_the_class_and_names_the_status(self):
        section, reg = self._section()
        client = _client({'section-registrations?': (503, {})})
        rows = gc.compare_section(
            client, section, [reg], {REG1}, final_type_id=FINAL,
            include_banner_only=True, registered=REGISTERED, last_sent={}, names={})
        self.assertEqual(rows[0]['Result'], gc.BANNER_ERROR)
        self.assertIn('503', rows[0]['Error'])


class ReportTests(TestCase):
    """The report end to end against the DB, Banner faked."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        for name in ('student', 'instructor'):
            Group.objects.get_or_create(name=name)
        User.objects.get_or_create(username='cron', defaults={'email': 'cron@example.com'})
        ay = AcademicYear.objects.create(name='AY compare')
        cls.term = Term.objects.create(academic_year=ay, code='FA90', label='Fall 2090')
        other_term = Term.objects.create(academic_year=ay, code='SP91', label='Spring 2091')
        course = Course.objects.create(
            catalog_number='101', title='Composition',
            cohort=Cohort.objects.create(name='C', designator='ENGL'), credit_hours=5)
        teacher = Teacher.objects.create(user=User.objects.create_user(
            username='cmp_t', email='cmp_t@x.org', password='x'))
        hs = HighSchool.objects.create(name='HS Compare')

        def section(term, number):
            return ClassSection.objects.create(
                class_number=number, section_number='01', term=term, course=course,
                teacher=teacher, external_sis_id=SECTION)

        def registration(sec, i, status, grade, sis_id):
            user = User.objects.create_user(
                username=f'cmp_s{i}', email=f'cmp_s{i}@x.org', password='x',
                first_name=f'S{i}', last_name='Student', psid=str(i))
            return StudentRegistration.objects.create(
                student=Student.objects.create(user=user), class_section=sec,
                highschool=hs, status=status, grade=grade, sis_id=sis_id,
                status_changed_on={'applied_on': '01/01/2090'})

        sec = section(cls.term, '90001')
        registration(sec, 1, 'registered', 'A', REG1)     # matches Banner
        registration(sec, 2, 'dropped', '', REG2)          # filtered out by status below
        registration(section(other_term, '90002'), 3, 'registered', 'B', REG3)  # other term

    def _run(self, **data):
        client = _client({
            'section-registrations?': (200, [_banner_reg(REG1),
                                             _banner_reg(REG2, 'notRegistered', 'dropped')]),
            'student-unverified-grades?': (200, [_banner_grade(REG1, 'A')]),
        })
        written = {}

        def save(path, content):
            written['csv'] = content.read().decode('utf-8')
            return path
        storage = MagicMock(save=save, url=lambda p: f'/media/{p}')
        task = SimpleNamespace(id='t1', created_by=None)
        with patch.object(gc, 'last_sent_map', return_value={}), \
                patch.object(grade_push, '_get_client', return_value=client), \
                patch.object(report_mod, 'PrivateMediaStorage', return_value=storage), \
                patch.object(report_mod, 'scope_report_by_campus', side_effect=lambda qs, *a, **k: qs):
            url = report_mod.banner_grade_comparison().run(task, data)
        return url, list(csv.DictReader(io.StringIO(written['csv'])))

    def test_selected_terms_and_statuses_only(self):
        url, rows = self._run(term=[str(self.term.id)], registration_status=['registered'],
                              include_banner_only=['on'])
        self.assertIn('banner_vs_myce_grades_', url)
        # REG2 is a MyCE registration filtered out by status: not "Only in Banner".
        self.assertEqual([(r['Result'], r['PSID']) for r in rows], [(gc.MATCH, '1')])
        self.assertEqual(rows[0]['Term Code'], 'FA90')
        self.assertEqual(rows[0]['CRN'], '90001')

    def test_only_differences_drops_matches(self):
        _, rows = self._run(term=[str(self.term.id)], only_differences=['on'])
        self.assertEqual(rows, [])

    def test_header_is_the_documented_columns(self):
        _, rows = self._run(term=[str(self.term.id)])
        self.assertEqual(tuple(rows[0].keys()), gc.COLUMNS)

    def test_form_requires_a_term(self):
        form = report_mod.banner_grade_comparison(None, {'campus': []})
        self.assertFalse(form.is_valid())
        self.assertIn('term', form.errors)

    def test_registered_in_both_app_configs(self):
        from .. import apps as ethos_apps
        for config in (ethos_apps.EthosConfig, ethos_apps.DevEthosConfig):
            self.assertEqual([r['name'] for r in config.REPORTS], ['banner_grade_comparison'])

"""import_sections_from_ethos --csv resolves the school by campus building code."""
import csv
import importlib.util
import tempfile
import uuid
from io import StringIO

from django.conf import settings
from django.test import TestCase, override_settings

from cis.campus_context import campus_context
from cis.models.course import Campus
from cis.models.highschool import HighSchool, HighSchoolCampus

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.management.commands.import_sections_from_ethos import Command
else:
    from ethos.management.commands.import_sections_from_ethos import Command


def _campus():
    code = f'{settings.CAMPUS_CODE_PREFIX}-{uuid.uuid4().hex[:6]}'
    return Campus.objects.create(name=f'C-{code}', code=code)


def _section(building):
    return {
        'id': 's1', 'code': '1', 'number': '01',
        'course': {'subject': {'abbreviation': 'ZZZ'}, 'number': '101'},
        'instructionalEvents': [{'locations': [{'location': {'building': {'code': building}}}]}],
        'scheduleAcademicPeriod': {}, 'instructorRosterDetails': [],
    }


def _status(campus, building):
    cmd = Command(stdout=StringIO())
    with tempfile.NamedTemporaryFile('r+', suffix='.csv') as f:
        if campus:
            with campus_context(campus):
                cmd._write_csv([_section(building)], f.name)
        else:
            cmd._write_csv([_section(building)], f.name)
        return list(csv.DictReader(open(f.name)))[0]['highschool_status']


class CsvHighSchoolStatusTests(TestCase):
    def setUp(self):
        self.a, self.b = _campus(), _campus()
        # Created in multi-campus mode outside any campus context, so cis does
        # not auto-link it. On a single-campus tenant the auto-link goes to the
        # deployment campus -- either of the two campuses above -- and then
        # collides with the link each test makes for itself.
        with override_settings(MULTI_CAMPUS=True):
            self.hs = HighSchool.objects.create(name='HS', code=f'H{uuid.uuid4().hex[:6]}',
                                                sau=f'S{uuid.uuid4().hex[:6]}')

    @override_settings(MULTI_CAMPUS=True)
    def test_multi_campus_matches_link_on_ambient_campus(self):
        HighSchoolCampus.objects.create(highschool=self.hs, campus=self.a, building_code='BX1')
        self.assertEqual(_status(self.a, 'BX1'), 'exists')

    @override_settings(MULTI_CAMPUS=True)
    def test_multi_campus_inactive_link_still_matches(self):
        HighSchoolCampus.objects.create(highschool=self.hs, campus=self.a,
                                        building_code='BX2', status='Inactive')
        self.assertEqual(_status(self.a, 'BX2'), 'exists')

    @override_settings(MULTI_CAMPUS=True)
    def test_multi_campus_other_campus_link_does_not_match(self):
        HighSchoolCampus.objects.create(highschool=self.hs, campus=self.b, building_code='BX3')
        self.assertEqual(_status(self.a, 'BX3'), 'not_found')

    @override_settings(MULTI_CAMPUS=True)
    def test_multi_campus_has_no_legacy_fallback(self):
        self.assertEqual(_status(self.a, self.hs.sau), 'not_found')

    @override_settings(MULTI_CAMPUS=False)
    def test_single_campus_falls_back_to_legacy_sau(self):
        self.assertEqual(_status(None, self.hs.sau), 'exists')

    @override_settings(MULTI_CAMPUS=False)
    def test_empty_building_code(self):
        self.assertEqual(_status(None, ''), 'no_building_code')

"""package-cis#168: Add Academic Year from SIS creates sub-terms under their
parent term, labelled "<Term> – <title>" as Pull Sub-Terms does (#167), so
sub-terms that share a title across terms no longer collide."""
import importlib.util
import json

from django.test import RequestFactory, TestCase

from cis.models.term import AcademicYear, Term

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.views.academic_periods import create_from_sis
else:
    from ethos.views.academic_periods import create_from_sis

YEAR = '99999999-9999-9999-9999-999999999999'
FALL = '22222222-2222-2222-2222-222222222222'
SPRING = '33333333-3333-3333-3333-333333333333'
FALL_FULL = '11111111-1111-1111-1111-111111111111'
SPRING_FULL = '44444444-4444-4444-4444-444444444444'
ORPHAN = '55555555-5555-5555-5555-555555555555'


def _period(guid, code, title, ptype, parent):
    return {'id': guid, 'code': code, 'title': title,
            'category': {'type': ptype, 'parent': {'id': parent}},
            'startOn': '2024-09-01', 'endOn': '2024-12-15'}


# the order the add page posts them in: each term, then its sub-terms
TERMS = [
    _period(FALL, '24FA', 'Fall', 'term', YEAR),
    _period(FALL_FULL, '24FA1', 'Full Term', 'subterm', FALL),
    _period(SPRING, '25SP', 'Spring', 'term', YEAR),
    _period(SPRING_FULL, '25SP1', 'Full Term', 'subterm', SPRING),
]


class CreateFromSisSubtermsTests(TestCase):

    def post(self, terms):
        body = {'year': {'id': YEAR, 'code': '2024', 'title': '2024-2025'},
                'terms': terms}
        request = RequestFactory().post(
            '/', data=json.dumps(body), content_type='application/json')
        response = create_from_sis(request)
        self.assertEqual(response.status_code, 200, response.content)
        return json.loads(response.content)

    def by_sis(self, guid):
        return Term.objects.get(external_sis_id=guid)

    def test_subterms_sharing_a_title_get_their_own_rows(self):
        self.post(TERMS)
        fall, spring = self.by_sis(FALL), self.by_sis(SPRING)
        self.assertEqual((fall.label, fall.parent), ('Fall', None))
        self.assertEqual((spring.label, spring.parent), ('Spring', None))
        fall_full, spring_full = self.by_sis(FALL_FULL), self.by_sis(SPRING_FULL)
        self.assertEqual((fall_full.label, fall_full.parent), ('Fall – Full Term', fall))
        self.assertEqual((spring_full.label, spring_full.parent),
                         ('Spring – Full Term', spring))
        self.assertEqual(spring_full.code, '25SP1')

    def test_running_it_again_does_not_duplicate(self):
        self.post(TERMS)
        self.post(TERMS)
        ay = AcademicYear.objects.get(external_sis_id=YEAR)
        self.assertEqual(Term.objects.filter(academic_year=ay).count(), 4)

    def test_subterm_already_pulled_is_updated_not_duplicated(self):
        ay = AcademicYear.objects.create(name='2024-2025', external_sis_id=YEAR)
        fall = Term.objects.create(academic_year=ay, label='Fall', code='24FA',
                                   external_sis_id=FALL)
        pulled = Term.objects.create(academic_year=ay, label='Fall – Full Term',
                                     code='24FA1', parent=fall, external_sis_id=FALL_FULL)
        self.post(TERMS)
        self.assertEqual(Term.objects.filter(external_sis_id=FALL_FULL).count(), 1)
        pulled.refresh_from_db()
        self.assertEqual((pulled.label, pulled.parent), ('Fall – Full Term', fall))

    def test_subterm_whose_parent_is_not_known_is_skipped(self):
        data = self.post([_period(ORPHAN, '24WI1', 'Full Term', 'subterm', FALL)])
        self.assertFalse(Term.objects.filter(external_sis_id=ORPHAN).exists())
        self.assertIn('skipped', data['message'])

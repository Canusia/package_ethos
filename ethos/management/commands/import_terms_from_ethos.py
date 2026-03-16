import logging

from django.core.management.base import BaseCommand

from ...library.ethos import Ethos

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    '''Import academic years and terms from Ethos.'''
    help = 'Look up an academic period by code in Ethos, then create the AcademicYear and its child Terms.'

    def add_arguments(self, parser):
        parser.add_argument('code', type=str, help='Academic period code to look up (e.g. "2025")')
        parser.add_argument('--create', action='store_true', help='Create/update records in local database')

    def handle(self, *args, **kwargs):
        code = kwargs['code']
        ethos = Ethos()

        # Look up the year-level academic period
        periods = ethos.get_academic_periods(code=code)
        if not periods:
            self.stdout.write(self.style.ERROR(f'No academic period found in Ethos for code "{code}".'))
            return

        year_period = periods[0]
        self.stdout.write(f"Academic Year: {year_period.get('title')}  {year_period.get('id')}")

        # Fetch child terms
        descendants = ethos.get_child_academic_periods(year_period['id'], depth=2)

        def build_tree(parent_id, items):
            children = []
            for item in items:
                item_parent = item.get('category', {}).get('parent', {}).get('id')
                if item_parent == parent_id:
                    children.append({
                        'period': item,
                        'children': build_tree(item['id'], items),
                    })
            return children

        tree = build_tree(year_period['id'], descendants)

        self.stdout.write(f'Found {len(tree)} child term(s):')
        for node in tree:
            term = node['period']
            self.stdout.write(
                f"  {term.get('code', '')}  {term.get('title', '')}  "
                f"{term.get('startOn', '')} - {term.get('endOn', '')}  {term.get('id', '')}"
            )
            for sub in node.get('children', []):
                subterm = sub['period']
                self.stdout.write(
                    f"    {subterm.get('code', '')}  {subterm.get('title', '')}  "
                    f"{subterm.get('startOn', '')} - {subterm.get('endOn', '')}  {subterm.get('id', '')}"
                )

        if not kwargs['create']:
            self.stdout.write(self.style.NOTICE('Dry run — pass --create to import into the database.'))
            return

        from cis.models.term import AcademicYear, Term

        academic_year = AcademicYear.get_or_add(
            name=year_period.get('title', year_period.get('code')),
            external_sis_id=year_period['id'],
            meta=year_period,
        )

        terms_created = 0
        for node in tree:
            term_data = node['period']
            dates = {}
            if term_data.get('startOn'):
                dates['start'] = term_data['startOn']
            if term_data.get('endOn'):
                dates['end'] = term_data['endOn']

            Term.get_or_add(
                academic_year=academic_year,
                label=term_data.get('title', term_data.get('code')),
                code=term_data.get('code', ''),
                external_sis_id=term_data['id'],
                meta=term_data,
                dates=dates,
            )
            terms_created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Created academic year "{academic_year.name}" with {terms_created} term(s).'
        ))

"""The term section import is the tenant's to override (package_ethos#11).

* A tenant SISImporter that defines ``fetch_and_import_sections(period_id, term)``
  owns the whole fetch + import: the task and the command hand it the period and term.
* Otherwise the package's generic fetch asks for a representation its importer
  contract parses: a preferred sections-maximum representation if one is set, else
  sections-maximum v16 explicitly (never a non-maximum preference).
* The package never overwrites a term action a tenant already registered under the
  same slug.
"""
import importlib.util
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from myce.component_registry import ActionRegistry

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos import tasks
    from ethos.ethos.views import sections
    P = 'ethos.ethos'
else:
    from ethos import tasks
    from ethos.views import sections
    P = 'ethos'

TERM = SimpleNamespace(pk=1, external_sis_id='p-1', code='202620',
                       academic_year=SimpleNamespace(campus=None))


MAX_V16_2 = 'application/vnd.hedtech.integration.sections-maximum.v16.2.0+json'
NON_MAX_V16_1 = 'application/vnd.hedtech.integration.v16.1.0+json'


class _TenantImporter:
    """A tenant importer that owns the whole term import."""
    calls = []

    def fetch_and_import_sections(self, period_id, term):
        self.calls.append((period_id, term))
        return {'section_created': 3}

    def import_sections(self, raw_sections, term, skip_certificates=False):
        raise AssertionError('the generic import must not run when the tenant owns it')


class _CertAwareImporter:
    """ctcd's shape: the hook accepts skip_certificates."""
    calls = []

    def fetch_and_import_sections(self, period_id, term, skip_certificates=False):
        self.calls.append((period_id, term, skip_certificates))
        return {'section_created': 1}


class _NoneImporter:
    """A tenant hook that forgets to return its counts."""

    def fetch_and_import_sections(self, period_id, term):
        return None


class _GenericImporter:
    def import_sections(self, raw_sections, term, skip_certificates=False):
        return {'section_created': len(raw_sections)}


def _service(importer_cls):
    return SimpleNamespace(SISImporter=importer_cls)


class SectionTaskOverrideTests(TestCase):
    def setUp(self):
        _TenantImporter.calls = []

    def _run(self, importer_cls, client):
        with patch('cis.models.term.Term.objects.get', return_value=TERM), \
             patch(f'{P}.library.ethos.Ethos', return_value=client), \
             patch('cis.services.tenant_services.get_tenant_service',
                   return_value=_service(importer_cls)):
            return tasks.import_sections_for_term.func(1)

    def test_a_hook_returning_none_yields_an_empty_counts_dict(self):
        self.assertEqual(self._run(_NoneImporter, MagicMock()), {})

    def test_tenant_hook_owns_the_whole_term_import(self):
        client = MagicMock()
        counts = self._run(_TenantImporter, client)
        self.assertEqual(_TenantImporter.calls, [('p-1', TERM)])
        self.assertEqual(counts, {'section_created': 3})
        client.get_sections.assert_not_called()

    def test_generic_fetch_passes_an_explicit_accept_header(self):
        client = MagicMock()
        client.get_sections.return_value = [{'id': 's1'}, {'id': 's2'}]
        counts = self._run(_GenericImporter, client)
        client.get_sections.assert_called_once_with(
            period_id='p-1', accept=tasks.SECTIONS_IMPORT_ACCEPT)
        self.assertIn('sections-maximum', tasks.SECTIONS_IMPORT_ACCEPT)
        self.assertEqual(counts, {'section_created': 2, 'total_fetched': 2})

    def test_a_preferred_maximum_representation_is_honoured(self):
        client = MagicMock()
        client.get_preferred_accept_header.return_value = MAX_V16_2
        client.get_sections.return_value = []
        self._run(_GenericImporter, client)
        client.get_preferred_accept_header.assert_called_with('sections')
        client.get_sections.assert_called_once_with(period_id='p-1', accept=MAX_V16_2)

    def test_a_preferred_non_maximum_representation_is_overridden(self):
        for preferred in (NON_MAX_V16_1, None):
            with self.subTest(preferred=preferred):
                client = MagicMock()
                client.get_preferred_accept_header.return_value = preferred
                client.get_sections.return_value = []
                self._run(_GenericImporter, client)
                client.get_sections.assert_called_once_with(
                    period_id='p-1', accept=tasks.SECTIONS_IMPORT_ACCEPT)


class SectionCommandOverrideTests(TestCase):
    def setUp(self):
        _TenantImporter.calls = []

    def test_create_delegates_to_the_tenant_hook(self):
        client = MagicMock()
        client.get_academic_period_id.return_value = 'p-1'
        term = SimpleNamespace(pk=1)
        with patch(f'{P}.management.commands.import_sections_from_ethos.Ethos', return_value=client), \
             patch('cis.models.term.Term.objects.filter') as flt, \
             patch('cis.services.tenant_services.get_tenant_service',
                   return_value=_service(_TenantImporter)):
            flt.return_value.first.return_value = term
            out = StringIO()
            call_command('import_sections_from_ethos', '202620', create=True, stdout=out)
        self.assertEqual(_TenantImporter.calls, [('p-1', term)])
        client.get_sections.assert_not_called()
        self.assertIn('section_created', out.getvalue())

    def test_create_runs_the_hook_inside_the_terms_campus(self):
        """The README promises the hook runs in the term's campus context; the
        command must set it like the task does (multi-campus tenants)."""
        from cis.campus_context import _current
        seen = []

        class _CampusImporter:
            def fetch_and_import_sections(self, period_id, term):
                seen.append(_current.get())
                return {'section_created': 1}

        campus = SimpleNamespace(pk=7, code='B')
        client = MagicMock()
        client.get_academic_period_id.return_value = 'p-1'
        term = SimpleNamespace(pk=1, academic_year=SimpleNamespace(campus=campus))
        with patch(f'{P}.management.commands.import_sections_from_ethos.Ethos', return_value=client), \
             patch('cis.models.term.Term.objects.filter') as flt, \
             patch('cis.services.tenant_services.get_tenant_service',
                   return_value=_service(_CampusImporter)):
            flt.return_value.first.return_value = term
            call_command('import_sections_from_ethos', '202620', create=True, stdout=StringIO())
        self.assertEqual(seen, [campus])

    def _create(self, importer_cls, **options):
        client = MagicMock()
        client.get_academic_period_id.return_value = 'p-1'
        term = SimpleNamespace(pk=1)
        out = StringIO()
        with patch(f'{P}.management.commands.import_sections_from_ethos.Ethos', return_value=client), \
             patch('cis.models.term.Term.objects.filter') as flt, \
             patch('cis.services.tenant_services.get_tenant_service',
                   return_value=_service(importer_cls)):
            flt.return_value.first.return_value = term
            call_command('import_sections_from_ethos', '202620', create=True, stdout=out, **options)
        return client, term, out.getvalue()

    def test_no_certificates_is_passed_to_a_hook_that_accepts_it(self):
        _CertAwareImporter.calls = []
        _, term, out = self._create(_CertAwareImporter, no_certificates=True)
        self.assertEqual(_CertAwareImporter.calls, [('p-1', term, True)])
        self.assertNotIn('is ignored', out)

    def test_hook_that_accepts_skip_certificates_gets_false_by_default(self):
        _CertAwareImporter.calls = []
        _, term, _ = self._create(_CertAwareImporter)
        self.assertEqual(_CertAwareImporter.calls, [('p-1', term, False)])

    def test_no_certificates_warns_when_the_hook_cannot_take_it(self):
        _, term, out = self._create(_TenantImporter, no_certificates=True)
        self.assertEqual(_TenantImporter.calls, [('p-1', term)])
        self.assertIn('--no-certificates is ignored', out)

    def test_a_hook_returning_none_does_not_crash_the_command(self):
        _, _, out = self._create(_NoneImporter)
        self.assertIn('returned no counts', out)

    def test_create_with_csv_and_a_hook_fetches_only_once(self):
        client, _, out = self._create(_TenantImporter, csv_path='/tmp/never-written.csv')
        client.get_sections.assert_not_called()
        self.assertIn('--csv is ignored', out)

    def test_dry_run_fetches_with_the_explicit_accept_header(self):
        client = MagicMock()
        client.get_academic_period_id.return_value = 'p-1'
        client.get_sections.return_value = []
        with patch(f'{P}.management.commands.import_sections_from_ethos.Ethos', return_value=client), \
             patch('cis.models.term.Term.objects.filter') as flt:
            flt.return_value.first.return_value = SimpleNamespace(pk=1)
            call_command('import_sections_from_ethos', '202620', stdout=StringIO())
        client.get_sections.assert_called_once_with(
            period_id='p-1', accept=tasks.SECTIONS_IMPORT_ACCEPT)

    def _dry_run(self, preferred):
        client = MagicMock()
        client.get_academic_period_id.return_value = 'p-1'
        client.get_preferred_accept_header.return_value = preferred
        client.get_sections.return_value = []
        with patch(f'{P}.management.commands.import_sections_from_ethos.Ethos', return_value=client), \
             patch('cis.models.term.Term.objects.filter') as flt:
            flt.return_value.first.return_value = SimpleNamespace(pk=1)
            call_command('import_sections_from_ethos', '202620', stdout=StringIO())
        return client

    def test_dry_run_honours_a_preferred_maximum_representation(self):
        client = self._dry_run(MAX_V16_2)
        client.get_sections.assert_called_once_with(period_id='p-1', accept=MAX_V16_2)

    def test_dry_run_overrides_a_preferred_non_maximum_representation(self):
        client = self._dry_run(NON_MAX_V16_1)
        client.get_sections.assert_called_once_with(
            period_id='p-1', accept=tasks.SECTIONS_IMPORT_ACCEPT)


class TermActionRegistrationTests(SimpleTestCase):
    def test_registers_the_package_action_when_the_slot_is_free(self):
        registry = ActionRegistry()
        sections.register_term_action(registry)
        action = registry._find_action('trigger_section_import')
        self.assertIs(action['handler'], sections.trigger_section_import)

    def test_never_overwrites_a_tenant_action_with_the_same_slug(self):
        registry = ActionRegistry()

        def tenant_handler(request):
            return None
        registry.action('sis', label='Pull Sections from SIS', scope=['detail'],
                        slug='trigger_section_import')(tenant_handler)
        sections.register_term_action(registry)
        self.assertIs(registry._find_action('trigger_section_import')['handler'], tenant_handler)


class LegacyRegistryTests(SimpleTestCase):
    """Older host ActionRegistry versions have no ``_find_action``; ``_groups`` is read instead."""

    def _registry(self, groups):
        registry = SimpleNamespace(_groups=groups, action=MagicMock())
        registry.action.return_value = lambda handler: handler
        return registry

    def test_a_tenant_action_in_groups_is_kept(self):
        registry = self._registry({'sis': {'actions': {'trigger_section_import': {'handler': object()}}}})
        sections.register_term_action(registry)
        registry.action.assert_not_called()

    def test_registers_when_groups_do_not_hold_the_slug(self):
        registry = self._registry({'sis': {'actions': {'other': {}}}, 'misc': {}})
        sections.register_term_action(registry)
        registry.action.assert_called_once()
        self.assertEqual(registry.action.call_args.args, ('sis',))

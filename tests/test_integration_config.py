"""
Integration configuration tests.

Verifies that the host Django project has correctly wired up the ethos app:
  - INSTALLED_APPS contains the right ethos app config
  - STATICFILES_DIRS includes the ethos staticfiles directory
  - EXTERNAL_SIS_IMPORTER is set
  - COLLEAGUE_AUTH_CODE is set
  - All ethos URL names are reversible
  - Component registry handler strings resolve to real callables
  - Component registry prefixes match the actual install mode (submodule vs pip)
"""

from importlib import import_module

from django.conf import settings
from django.test import TestCase
from django.urls import reverse, NoReverseMatch


class InstalledAppsTest(TestCase):
    """ethos app config must be present in INSTALLED_APPS."""

    def test_ethos_app_installed(self):
        app_labels = [app.name for app in __import__('django.apps', fromlist=['apps']).apps.get_app_configs()]
        ethos_names = {'ethos', 'ethos.ethos'}
        self.assertTrue(
            ethos_names & set(app_labels),
            f"Neither 'ethos' nor 'ethos.ethos' found in installed apps. Got: {app_labels}",
        )

    def test_correct_app_config_for_mode(self):
        import importlib.util
        from django.apps import apps
        ethos_configs = [c for c in apps.get_app_configs() if c.name in ('ethos', 'ethos.ethos')]
        self.assertTrue(ethos_configs, "No ethos AppConfig found.")
        cfg = ethos_configs[0]

        submodule_installed = importlib.util.find_spec('ethos.ethos') is not None
        if submodule_installed:
            self.assertEqual(
                cfg.name, 'ethos.ethos',
                "Submodule detected: expected DevEthosConfig (name='ethos.ethos'), "
                f"got name='{cfg.name}' ({type(cfg).__name__})"
            )
        else:
            self.assertEqual(
                cfg.name, 'ethos',
                "Pip install detected: expected EthosConfig (name='ethos'), "
                f"got name='{cfg.name}' ({type(cfg).__name__})"
            )


class StaticFilesTest(TestCase):
    """ethos staticfiles directory must be in STATICFILES_DIRS."""

    def test_ethos_staticfiles_in_dirs(self):
        dirs = [str(d) for d in getattr(settings, 'STATICFILES_DIRS', []) if d]
        match = any('ethos' in d for d in dirs)
        self.assertTrue(
            match,
            f"No ethos path found in STATICFILES_DIRS. Got: {dirs}",
        )

    def test_ethos_staticfiles_dir_exists(self):
        import os
        dirs = [str(d) for d in getattr(settings, 'STATICFILES_DIRS', []) if d and 'ethos' in str(d)]
        self.assertTrue(dirs, "No ethos entry in STATICFILES_DIRS.")
        for d in dirs:
            self.assertTrue(
                os.path.isdir(d),
                f"ethos staticfiles directory does not exist on disk: {d}",
            )


class SettingsTest(TestCase):
    """Required settings must be present and non-empty."""

    def test_external_sis_importer_set(self):
        value = getattr(settings, 'EXTERNAL_SIS_IMPORTER', None)
        self.assertIsNotNone(value, "EXTERNAL_SIS_IMPORTER is not set in settings.")
        self.assertNotEqual(value.strip(), '', "EXTERNAL_SIS_IMPORTER must not be empty.")

    def test_colleague_auth_code_set(self):
        value = getattr(settings, 'COLLEAGUE_AUTH_CODE', None)
        self.assertIsNotNone(value, "COLLEAGUE_AUTH_CODE is not set in settings.")
        self.assertNotEqual(value.strip(), '', "COLLEAGUE_AUTH_CODE must not be empty.")

    def test_external_sis_importer_module_exists(self):
        import importlib.util
        slug = getattr(settings, 'EXTERNAL_SIS_IMPORTER', '')
        if not slug:
            self.skipTest("EXTERNAL_SIS_IMPORTER not set.")
        submodule_installed = importlib.util.find_spec('ethos.ethos') is not None
        module_path = (
            f'ethos.ethos.library.importer.{slug}.section_import'
            if submodule_installed
            else f'ethos.library.importer.{slug}.section_import'
        )
        try:
            import_module(module_path)
        except ModuleNotFoundError as exc:
            self.fail(
                f"EXTERNAL_SIS_IMPORTER='{slug}' but no importer module found at "
                f"'{module_path}': {exc}"
            )


class UrlsTest(TestCase):
    """All ethos URL names must be reversible under the 'ethos' namespace."""

    EXPECTED_URLS = [
        ('ethos:ethos_status', []),
        ('ethos:ethos_run_method', []),
        ('ethos:lookup_academic_period', []),
        ('ethos:academic_year_create_from_sis', []),
        ('ethos:ethos_section_import', []),
        ('ethos:ethos_section_import_status', []),
    ]

    def test_all_url_names_reversible(self):
        for name, args in self.EXPECTED_URLS:
            with self.subTest(url_name=name):
                try:
                    url = reverse(name, args=args)
                    self.assertTrue(url.startswith('/'), f"Reversed URL looks wrong: {url}")
                except NoReverseMatch as exc:
                    self.fail(f"Could not reverse '{name}': {exc}")

    def test_ethos_urls_under_ce_prefix(self):
        url = reverse('ethos:ethos_status')
        self.assertIn('/ce/ethos/', url, f"Expected URL under /ce/ethos/, got: {url}")


class ComponentRegistryTest(TestCase):
    """Component registry handler strings must resolve to real callables."""

    EXPECTED_HANDLERS = [
        # (registry module, action slug, expected function name)
        ('myce.component_registry.academic_year', 'lookup_guid',            'lookup_guid'),
        ('myce.component_registry.academic_year', 'lookup_academic_period',  'lookup_academic_period'),
        ('myce.component_registry.academic_year', 'create_from_sis',         'create_from_sis'),
        ('myce.component_registry.term',          'pull_sections',            'trigger_section_import'),
        ('myce.component_registry.cohort',        'lookup_subjects',          'lookup_subjects'),
        ('myce.component_registry.cohort',        'create_from_sis',          'create_from_sis'),
    ]

    def _get_registry(self, module_path):
        mod = import_module(module_path)
        # Find the ActionRegistry instance in the module
        from myce.component_registry import ActionRegistry
        for attr in vars(mod).values():
            if isinstance(attr, ActionRegistry):
                return attr
        return None

    def test_registry_modules_importable(self):
        for module_path, _, _ in self.EXPECTED_HANDLERS:
            with self.subTest(module=module_path):
                try:
                    import_module(module_path)
                except ImportError as exc:
                    self.fail(f"Cannot import registry module '{module_path}': {exc}")

    def test_handler_strings_resolve(self):
        for module_path, slug, func_name in self.EXPECTED_HANDLERS:
            with self.subTest(registry=module_path, action=slug):
                registry = self._get_registry(module_path)
                self.assertIsNotNone(registry, f"No ActionRegistry found in {module_path}")

                action = registry._find_action(slug)
                self.assertIsNotNone(action, f"Action '{slug}' not found in {module_path}")

                handler_path = action.get('handler', '')
                self.assertTrue(handler_path, f"Action '{slug}' has no handler.")

                try:
                    mod_path, fn = handler_path.rsplit('.', 1)
                    mod = import_module(mod_path)
                    callable_ = getattr(mod, fn, None)
                    self.assertIsNotNone(
                        callable_,
                        f"Function '{fn}' not found in module '{mod_path}' "
                        f"(handler: '{handler_path}')",
                    )
                    self.assertTrue(
                        callable(callable_),
                        f"Handler '{handler_path}' is not callable.",
                    )
                except (ModuleNotFoundError, ImportError) as exc:
                    self.fail(
                        f"Handler '{handler_path}' for action '{slug}' "
                        f"in '{module_path}' could not be imported: {exc}"
                    )

    def test_handler_prefix_matches_install_mode(self):
        """Handler module paths must use ethos.ethos (submodule) or ethos (pip)."""
        import importlib.util
        submodule_installed = importlib.util.find_spec('ethos.ethos') is not None
        expected_prefix = 'ethos.ethos' if submodule_installed else 'ethos'
        wrong_prefix = 'ethos' if submodule_installed else 'ethos.ethos'

        for module_path, slug, _ in self.EXPECTED_HANDLERS:
            registry = self._get_registry(module_path)
            if registry is None:
                continue
            action = registry._find_action(slug)
            if action is None:
                continue
            handler = action.get('handler', '')
            with self.subTest(handler=handler):
                self.assertTrue(
                    handler.startswith(expected_prefix),
                    f"Handler '{handler}' should start with '{expected_prefix}' "
                    f"(submodule_installed={submodule_installed}), not '{wrong_prefix}'.",
                )

"""Config defaults so a tenant that sets nothing still works."""
import importlib.util

from django.test import TestCase, override_settings

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.consume import config
else:
    from ethos.consume import config


# TestCase, not SimpleTestCase: consume_limit()/max_batches() consult the
# operator-facing `ethos.settings.ethos_consume` Setting before falling back to
# these Django-settings keys, so they touch the DB. The assertions below run
# with no Setting row present, which is exactly the fallback path.
class ConfigDefaultTests(TestCase):
    def test_defaults(self):
        self.assertEqual(config.consume_limit(), 100)
        self.assertEqual(config.retention_days(), 30)
        self.assertEqual(config.log_retention_days(), 90)
        self.assertEqual(config.handler_paths(), {})
        self.assertFalse(config.auto_consume_enabled('section-registrations'))

    @override_settings(ETHOS_CONSUME_LIMIT=250, ETHOS_CONSUME_RETENTION_DAYS=60,
                       ETHOS_LOG_RETENTION_DAYS=120)
    def test_overrides(self):
        self.assertEqual(config.consume_limit(), 250)
        self.assertEqual(config.retention_days(), 60)
        self.assertEqual(config.log_retention_days(), 120)

    @override_settings(ETHOS_CONSUME_AUTO={'section-registrations': True})
    def test_auto_consume_enabled_per_resource(self):
        self.assertTrue(config.auto_consume_enabled('section-registrations'))
        self.assertFalse(config.auto_consume_enabled('courses'))

    @override_settings(ETHOS_CONSUME_HANDLERS={'courses': 'x.Y'})
    def test_handler_paths(self):
        self.assertEqual(config.handler_paths(), {'courses': 'x.Y'})

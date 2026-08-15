"""Handlers are resolved by dotted path from settings — the tenant owns policy."""
import importlib.util

from django.test import SimpleTestCase, override_settings

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.consume.base import ConsumeHandler, Plan, Change
    from ethos.ethos.consume.registry import get_handler
else:
    from ethos.consume.base import ConsumeHandler, Plan, Change
    from ethos.consume.registry import get_handler


class StubHandler(ConsumeHandler):
    resource_name = 'section-registrations'

    def plan(self, message):
        return Plan(action='noop', summary='nothing to do')

    def apply(self, message, plan):
        raise AssertionError('not called in these tests')


HANDLER_PATH = f'{__name__}.StubHandler'


class RegistryTests(SimpleTestCase):
    def test_returns_none_when_no_handler_configured(self):
        self.assertIsNone(get_handler('section-registrations'))

    @override_settings(ETHOS_CONSUME_HANDLERS={'section-registrations': HANDLER_PATH})
    def test_resolves_dotted_path_to_an_instance(self):
        handler = get_handler('section-registrations')
        self.assertIsInstance(handler, StubHandler)

    @override_settings(ETHOS_CONSUME_HANDLERS={'section-registrations': HANDLER_PATH})
    def test_unconfigured_resource_is_none(self):
        self.assertIsNone(get_handler('courses'))

    @override_settings(ETHOS_CONSUME_HANDLERS={'courses': 'nope.NotReal'})
    def test_bad_path_raises_with_a_useful_message(self):
        with self.assertRaises(ImportError):
            get_handler('courses')


class PlanTests(SimpleTestCase):
    def test_defaults(self):
        plan = Plan(action='status_updated', summary='drop it')
        self.assertEqual(plan.changes, [])
        self.assertFalse(plan.blocked)
        self.assertEqual(plan.reason, '')

    def test_changes_are_independent_between_instances(self):
        a = Plan(action='x', summary='x')
        a.changes.append(Change('status', 'registered', 'dropped'))
        b = Plan(action='y', summary='y')
        self.assertEqual(b.changes, [])

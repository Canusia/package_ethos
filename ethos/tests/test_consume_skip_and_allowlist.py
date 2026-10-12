"""package_ethos#6: handlers can report SKIPPED; the Setting form shows the code allowlist."""
import importlib.util
from io import StringIO

from django.core.management import call_command
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.consume import config
    from ethos.ethos.consume.base import ConsumeHandler, Plan, Result
    from ethos.ethos.consume.service import consume_message
    from ethos.ethos.models import EthosMessage
    from ethos.ethos.settings.ethos_consume import ethos_consume
else:  # pragma: no cover - flat pip layout
    from ethos.consume import config
    from ethos.consume.base import ConsumeHandler, Plan, Result
    from ethos.consume.service import consume_message
    from ethos.models import EthosMessage
    from ethos.settings.ethos_consume import ethos_consume

APPLIED = []


class NotMineHandler(ConsumeHandler):
    resource_name = 'section-registrations'

    def plan(self, message):
        return Plan(action='not_myce', summary='section is not a MyCE section',
                    skip=True, reason='no local section for this registration')

    def apply(self, message, plan):
        APPLIED.append(message.pk)
        return Result(action=plan.action, detail=plan.summary)


HANDLERS = {'section-registrations': f'{__name__}.NotMineHandler'}


def _message():
    return EthosMessage.objects.create(queue_id=1, resource_name='section-registrations',
                                       resource_id='guid-1', operation='replaced', payload={})


@override_settings(MULTI_CAMPUS=False, ETHOS_CONSUME_HANDLERS=HANDLERS)
class HandlerSkipTests(TestCase):
    def setUp(self):
        APPLIED.clear()

    def test_skip_plan_records_skipped_without_applying(self):
        msg = _message()
        plan = consume_message(msg)
        msg.refresh_from_db()

        self.assertTrue(plan.skip)
        self.assertEqual(msg.status, EthosMessage.SKIPPED)
        self.assertEqual(msg.action, 'not_myce')
        self.assertIn('no local section', msg.action_detail)
        self.assertIsNotNone(msg.consumed_at)
        self.assertEqual(APPLIED, [])

    def test_dry_run_returns_the_skip_plan_and_writes_nothing(self):
        msg = _message()
        plan = consume_message(msg, dry_run=True)
        msg.refresh_from_db()

        self.assertTrue(plan.skip)
        self.assertEqual(msg.status, EthosMessage.PENDING)

    def test_dry_run_command_marks_skip(self):
        _message()
        out = StringIO()
        call_command('process_ethos_messages', '--dry-run', '--force', stdout=out)
        self.assertIn('[SKIP]', out.getvalue())

    def test_plan_default_is_not_skip(self):
        self.assertFalse(Plan(action='a', summary='s').skip)


class AllowlistSummaryTests(SimpleTestCase):
    @override_settings(ETHOS_CONSUME_HANDLERS={'section-registrations': 'x.H', 'courses': 'x.C'},
                       ETHOS_CONSUME_AUTO={'section-registrations': True, 'persons': True})
    def test_lists_handled_resources_with_allowlist_state(self):
        self.assertEqual(config.handled_resources(),
                         [('courses', False), ('section-registrations', True)])

    @override_settings(ETHOS_CONSUME_HANDLERS={}, ETHOS_CONSUME_AUTO={})
    def test_empty_when_no_handlers(self):
        self.assertEqual(config.handled_resources(), [])


@override_settings(MULTI_CAMPUS=False)
class SettingFormAllowlistTests(TestCase):
    def _form(self):
        return ethos_consume(RequestFactory().get('/ce/settings/', {'report_id': 1}))

    @override_settings(ETHOS_CONSUME_HANDLERS={'section-registrations': 'x.H', 'courses': 'x.C'},
                       ETHOS_CONSUME_AUTO={'section-registrations': True})
    def test_help_text_lists_what_will_and_will_not_consume(self):
        help_text = str(self._form().fields['consume_after_poll'].help_text)
        self.assertIn('section-registrations', help_text)
        self.assertIn('courses', help_text)
        self.assertIn('ETHOS_CONSUME_AUTO', help_text)

    @override_settings(ETHOS_CONSUME_HANDLERS={}, ETHOS_CONSUME_AUTO={})
    def test_help_text_says_nothing_is_handled(self):
        help_text = str(self._form().fields['consume_after_poll'].help_text)
        self.assertIn('No handlers are configured', help_text)

    @override_settings(ETHOS_CONSUME_HANDLERS={'courses': 'x.C'}, ETHOS_CONSUME_AUTO={})
    def test_summary_is_not_saved_into_the_setting(self):
        form = self._form()
        self.assertNotIn('handled_resources', form.fields)

    @override_settings(ETHOS_CONSUME_HANDLERS={'courses': 'x.C'}, ETHOS_CONSUME_AUTO={})
    def test_help_text_markup_is_safe_and_rendered(self):
        html = self._form().as_p()
        self.assertIn('<code>courses</code>', html)

"""Dispatch: plan/apply, status recording, and the dry-run guarantee."""
import importlib.util

from django.test import TestCase, override_settings

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.consume.base import ConsumeHandler, Plan, Change, Result
    from ethos.ethos.consume.service import consume_message
    from ethos.ethos.models import EthosMessage
else:
    from ethos.consume.base import ConsumeHandler, Plan, Change, Result
    from ethos.consume.service import consume_message
    from ethos.models import EthosMessage

APPLIED = []


class RecordingHandler(ConsumeHandler):
    resource_name = 'section-registrations'

    def plan(self, message):
        return Plan(
            action='status_updated',
            summary='registered -> dropped',
            changes=[Change('status', 'registered', 'dropped')],
            target_type='cis.StudentRegistration', target_pk='42',
            target_label='Ada Lovelace / MATH-101',
        )

    def apply(self, message, plan):
        APPLIED.append(message.pk)
        return Result(action=plan.action, detail=plan.summary,
                      target_type=plan.target_type, target_pk=plan.target_pk,
                      target_label=plan.target_label)


class BlockingHandler(RecordingHandler):
    def plan(self, message):
        return Plan(action='unknown_registration', summary='no local record',
                    blocked=True, reason='no StudentRegistration with that sis_id')


class ExplodingHandler(RecordingHandler):
    def apply(self, message, plan):
        raise RuntimeError('handler blew up')


class PartiallyApplyingExplodingHandler(RecordingHandler):
    """Writes a real row, then blows up -- proves apply() rolls back."""

    def apply(self, message, plan):
        EthosMessage.objects.create(
            queue_id=999, resource_name='sentinel', resource_id='sentinel-1',
            operation='created', payload={})
        raise RuntimeError('handler blew up')


def _path(cls):
    return f'{__name__}.{cls.__name__}'


def _message(**kwargs):
    defaults = dict(queue_id=1, resource_name='section-registrations',
                    resource_id='guid-1', operation='replaced', payload={})
    defaults.update(kwargs)
    return EthosMessage.objects.create(**defaults)


class ConsumeServiceTests(TestCase):
    def setUp(self):
        APPLIED.clear()

    @override_settings(ETHOS_CONSUME_HANDLERS={})
    def test_no_handler_marks_skipped(self):
        msg = _message()
        consume_message(msg)
        msg.refresh_from_db()

        self.assertEqual(msg.status, EthosMessage.SKIPPED)
        self.assertEqual(msg.action, 'no_handler')
        self.assertIsNotNone(msg.consumed_at)

    @override_settings(ETHOS_CONSUME_HANDLERS={
        'section-registrations': f'{__name__}.RecordingHandler'})
    def test_consumes_and_records_the_result(self):
        msg = _message()
        consume_message(msg)
        msg.refresh_from_db()

        self.assertEqual(msg.status, EthosMessage.CONSUMED)
        self.assertEqual(msg.action, 'status_updated')
        self.assertEqual(msg.target_type, 'cis.StudentRegistration')
        self.assertEqual(msg.target_pk, '42')
        self.assertEqual(msg.target_label, 'Ada Lovelace / MATH-101')
        self.assertIsNotNone(msg.consumed_at)
        self.assertEqual(APPLIED, [msg.pk])

    @override_settings(ETHOS_CONSUME_HANDLERS={
        'section-registrations': f'{__name__}.RecordingHandler'})
    def test_dry_run_writes_nothing(self):
        msg = _message()

        plan = consume_message(msg, dry_run=True)
        msg.refresh_from_db()

        self.assertEqual(plan.action, 'status_updated')
        self.assertEqual(msg.status, EthosMessage.PENDING)
        self.assertIsNone(msg.consumed_at)
        self.assertEqual(msg.action, '')
        self.assertEqual(msg.target_type, '')
        self.assertEqual(msg.target_pk, '')
        self.assertEqual(msg.target_label, '')
        self.assertEqual(APPLIED, [])

    @override_settings(ETHOS_CONSUME_HANDLERS={
        'section-registrations': f'{__name__}.BlockingHandler'})
    def test_blocked_plan_flags_without_applying(self):
        msg = _message()
        consume_message(msg)
        msg.refresh_from_db()

        self.assertEqual(msg.status, EthosMessage.FLAGGED)
        self.assertEqual(msg.action, 'unknown_registration')
        self.assertIn('no StudentRegistration', msg.action_detail)
        self.assertEqual(APPLIED, [])

    @override_settings(ETHOS_CONSUME_HANDLERS={
        'section-registrations': f'{__name__}.ExplodingHandler'})
    def test_handler_failure_marks_failed_and_records_error(self):
        msg = _message()
        consume_message(msg)
        msg.refresh_from_db()

        self.assertEqual(msg.status, EthosMessage.FAILED)
        self.assertIn('handler blew up', msg.error)
        self.assertIsNotNone(msg.consumed_at)

    @override_settings(ETHOS_CONSUME_HANDLERS={
        'section-registrations': f'{__name__}.PartiallyApplyingExplodingHandler'})
    def test_apply_failure_rolls_back_partial_writes(self):
        msg = _message()
        consume_message(msg)
        msg.refresh_from_db()

        self.assertEqual(msg.status, EthosMessage.FAILED)
        self.assertIn('handler blew up', msg.error)
        self.assertFalse(
            EthosMessage.objects.filter(queue_id=999, resource_name='sentinel').exists())

    @override_settings(ETHOS_CONSUME_HANDLERS={
        'section-registrations': f'{__name__}.RecordingHandler'})
    def test_rerun_overwrites_the_single_result(self):
        msg = _message(status=EthosMessage.FAILED, error='old failure',
                       action='old_action')

        consume_message(msg, force=True)
        msg.refresh_from_db()

        self.assertEqual(msg.status, EthosMessage.CONSUMED)
        self.assertEqual(msg.action, 'status_updated')
        self.assertEqual(msg.error, '')

    @override_settings(ETHOS_CONSUME_HANDLERS={
        'section-registrations': f'{__name__}.RecordingHandler'})
    def test_already_consumed_message_is_not_reconsumed_without_force(self):
        msg = _message(status=EthosMessage.CONSUMED)

        consume_message(msg)

        self.assertEqual(APPLIED, [])

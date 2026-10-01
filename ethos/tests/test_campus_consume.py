"""Queue and messages are per campus (package_ethos#4)."""
import importlib.util
import uuid
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings

from cis.models.course import Campus

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.consume.poller import poll, CursorNotInitialised
    from ethos.ethos.models import EthosMessage, EthosConsumeCursor
    from ethos.ethos.tests.test_consume_poller import fake_client, load_sample
else:
    from ethos.consume.poller import poll, CursorNotInitialised
    from ethos.models import EthosMessage, EthosConsumeCursor
    from ethos.tests.test_consume_poller import fake_client, load_sample


def _campus():
    code = f'{settings.CAMPUS_CODE_PREFIX}-{uuid.uuid4().hex[:6]}'
    return Campus.objects.create(name=f'C-{code}', code=code)


@override_settings(MULTI_CAMPUS=True)
class CampusPollTests(TestCase):
    def setUp(self):
        self.a, self.b = _campus(), _campus()
        self.sample = load_sample()

    def test_poll_stores_for_the_clients_campus_and_advances_only_its_cursor(self):
        EthosConsumeCursor.load(self.a)
        EthosConsumeCursor.load(self.b)

        result = poll(client=fake_client([self.sample], campus=self.a), limit=100)

        self.assertEqual(result['stored'], 27)
        self.assertEqual(EthosMessage.objects.filter(campus=self.a).count(), 27)
        self.assertEqual(EthosMessage.objects.exclude(campus=self.a).count(), 0)
        self.assertEqual(EthosConsumeCursor.load(self.a).last_processed_id, 27)
        self.assertEqual(EthosConsumeCursor.load(self.b).last_processed_id, 0)

    def test_same_queue_id_is_not_a_duplicate_across_campuses(self):
        poll(client=fake_client([self.sample], campus=self.a), limit=100, from_id=0)
        result = poll(client=fake_client([self.sample], campus=self.b), limit=100, from_id=0)

        self.assertEqual(result['stored'], 27)
        self.assertEqual(EthosMessage.objects.count(), 54)

    def test_no_cursor_row_refuses_rather_than_replaying_the_queue(self):
        client = fake_client([self.sample], campus=self.a)

        with self.assertRaises(CursorNotInitialised) as ctx:
            poll(client=client, limit=100)

        self.assertIn('assign_ethos_campus', str(ctx.exception))
        self.assertIn('--from-id', str(ctx.exception))
        client.get_messages.assert_not_called()
        self.assertFalse(EthosConsumeCursor.objects.filter(campus=self.a).exists())
        self.assertEqual(EthosMessage.objects.count(), 0)

    def test_from_id_zero_initialises_the_cursor(self):
        poll(client=fake_client([self.sample], campus=self.a), limit=100, from_id=0)

        self.assertTrue(EthosConsumeCursor.objects.filter(campus=self.a).exists())
        self.assertEqual(EthosConsumeCursor.load(self.a).last_processed_id, 27)


@override_settings(MULTI_CAMPUS=False)
class SingleCampusPollTests(TestCase):
    def test_singleton_cursor_is_auto_created(self):
        self.assertFalse(EthosConsumeCursor.objects.exists())

        result = poll(client=fake_client([load_sample()], campus=None), limit=100)

        self.assertEqual(result['stored'], 27)
        self.assertEqual(EthosMessage.objects.filter(campus__isnull=True).count(), 27)
        self.assertEqual(EthosConsumeCursor.load().last_processed_id, 27)


@override_settings(MULTI_CAMPUS=True)
class CampusProcessTests(TestCase):
    def setUp(self):
        self.a, self.b = _campus(), _campus()
        for n, campus in ((1, self.a), (2, self.b)):
            EthosMessage.objects.create(
                queue_id=n, resource_name='widgets', resource_id='x',
                operation='created', campus=campus)

    def test_process_handles_only_the_given_campus(self):
        seen = []
        with patch('ethos.ethos.management.commands.process_ethos_messages.consume_message'
                   if importlib.util.find_spec('ethos.ethos')
                   else 'ethos.management.commands.process_ethos_messages.consume_message',
                   side_effect=lambda m, **kw: seen.append(m.pk)), \
                patch('ethos.ethos.consume.config.auto_consume_enabled' if
                      importlib.util.find_spec('ethos.ethos')
                      else 'ethos.consume.config.auto_consume_enabled', return_value=True):
            call_command('process_ethos_messages', campus=self.b.code, stdout=StringIO())

        self.assertEqual(seen, [EthosMessage.objects.get(campus=self.b).pk])

    def test_process_by_id_cannot_reach_another_campus(self):
        other = EthosMessage.objects.get(campus=self.a)
        mod = ('ethos.ethos' if importlib.util.find_spec('ethos.ethos') else 'ethos')
        with patch(f'{mod}.management.commands.process_ethos_messages.consume_message') as cm:
            call_command('process_ethos_messages', campus=self.b.code, id=other.pk,
                         stdout=StringIO())
        cm.assert_not_called()


@override_settings(MULTI_CAMPUS=True)
class CampusFromIdEmptyQueueTests(TestCase):
    def test_from_id_on_an_empty_queue_still_initialises_the_cursor(self):
        campus = _campus()

        poll(client=fake_client([[]], campus=campus), limit=100, from_id=5)

        self.assertEqual(EthosConsumeCursor.load(campus).last_processed_id, 5)
        poll(client=fake_client([[]], campus=campus), limit=100)

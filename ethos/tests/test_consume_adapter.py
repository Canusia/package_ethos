"""The adapter is the only code that knows Ethos envelope field names."""
import importlib.util
import json
import os

from django.test import SimpleTestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.consume.adapter import parse_notification
else:
    from ethos.consume.adapter import parse_notification

FIXTURE = os.path.join(
    os.path.dirname(__file__), 'fixtures',
    'ctc-section-registration-notifications.json',
)


def load_sample():
    with open(FIXTURE) as fh:
        return json.load(fh)


class ParseNotificationTests(SimpleTestCase):
    def setUp(self):
        self.sample = load_sample()

    def test_sample_is_the_verified_27(self):
        self.assertEqual(len(self.sample), 27)

    def test_extracts_envelope_fields(self):
        parsed = parse_notification(self.sample[0])

        self.assertEqual(parsed['queue_id'], 1)
        self.assertEqual(parsed['resource_name'], 'section-registrations')
        self.assertEqual(parsed['resource_id'], '39c6781e-5537-4f4e-9b74-7d48e70d7b4a')
        self.assertEqual(parsed['resource_version'],
                         'application/vnd.hedtech.integration.v16.2.0+json')
        self.assertEqual(parsed['operation'], 'replaced')
        self.assertEqual(parsed['content_type'], 'resource-representation')
        self.assertEqual(parsed['message_type'], 'change-notification')
        self.assertEqual(parsed['publisher_id'], '97a97f35-f83e-4d27-b19b-0902f80fd158')

    def test_queue_id_is_int_from_string(self):
        self.assertIsInstance(parse_notification(self.sample[0])['queue_id'], int)

    def test_parses_space_separated_published_timestamp(self):
        parsed = parse_notification(self.sample[0])
        self.assertEqual(parsed['published_on'].year, 2026)
        self.assertEqual(parsed['published_on'].month, 8)
        self.assertEqual(parsed['published_on'].day, 12)
        self.assertIsNotNone(parsed['published_on'].tzinfo)

    def test_optional_fields_present(self):
        parsed = parse_notification(self.sample[0])
        self.assertEqual(parsed['sis_message_id'], '5704543')
        self.assertIsNotNone(parsed['initiated_on'])

    def test_optional_fields_absent_do_not_raise(self):
        raw = dict(self.sample[0])
        raw.pop('messageId', None)
        raw.pop('initiated', None)

        parsed = parse_notification(raw)

        self.assertEqual(parsed['sis_message_id'], '')
        self.assertIsNone(parsed['initiated_on'])

    def test_payload_is_stored_verbatim(self):
        self.assertEqual(parse_notification(self.sample[0])['payload'], self.sample[0])

    def test_every_sample_notification_parses(self):
        for raw in self.sample:
            parsed = parse_notification(raw)
            self.assertIsInstance(parsed['queue_id'], int)
            self.assertEqual(parsed['resource_name'], 'section-registrations')
            self.assertIn(parsed['operation'], ('created', 'replaced'))
            self.assertTrue(parsed['payload'])

    def test_missing_resource_block_degrades_gracefully(self):
        parsed = parse_notification({'id': '5', 'operation': 'deleted'})

        self.assertEqual(parsed['queue_id'], 5)
        self.assertEqual(parsed['resource_name'], '')
        self.assertEqual(parsed['resource_id'], '')
        self.assertEqual(parsed['operation'], 'deleted')

    def test_non_numeric_queue_id_raises(self):
        with self.assertRaises(ValueError):
            parse_notification({'id': 'not-a-number'})

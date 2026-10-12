"""package_ethos#3 (5): code-table reads and populate_sis_guids. Ported from SCCC."""
import importlib.util
import json
from unittest.mock import patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from cis.models.settings import Setting
from cis.settings.sis_settings import sis_settings

from . import PKG

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos import reference
    from ethos.ethos.reference import RESOURCES, build_guid_map, load_guids_blob, merge_guids
else:  # pragma: no cover - flat pip layout
    from ethos import reference
    from ethos.reference import RESOURCES, build_guid_map, load_guids_blob, merge_guids


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.ok = 200 <= status < 300
        self.text = json.dumps(payload) if isinstance(payload, (list, dict)) else str(payload)

    def json(self):
        if isinstance(self._payload, (list, dict)):
            return self._payload
        raise ValueError('not json')


def _race(rid, code, title, category):
    return {'id': rid, 'code': code, 'title': title,
            'reporting': [{'country': {'code': 'USA', 'racialCategory': category}}]}


#: Trimmed from SCCC's live Ethos.
RACES = [
    _race('r-white', '1', 'White', 'white'),
    _race('r-black', '2', 'Black/African American', 'blackOrAfricanAmerican'),
    _race('r-asian', '3', 'Asian', 'asian'),
    _race('r-hawaii', '4', 'Native Hawaiian or Pacific Islander', 'hawaiianOrPacificIslander'),
    _race('r-amind', '5', 'American Indian/Alaskan Native', 'americanIndianOrAlaskaNative'),
]
ETHNICITIES = [
    {'id': 'e-non', 'title': 'Not Hispanic or Latino',
     'reporting': [{'country': {'code': 'USA', 'ethnicCategory': 'nonHispanic'}}]},
    {'id': 'e-his', 'title': 'Hispanic or Latino',
     'reporting': [{'country': {'code': 'USA', 'ethnicCategory': 'hispanic'}}]},
]
PHONE_TYPES = [
    {'id': 'p-ce', 'code': 'CE', 'title': 'Cell', 'type': 'mobile'},
    {'id': 'p-pr', 'code': 'PR', 'title': 'Home'},
    {'id': 'p-pa', 'code': 'PA', 'title': 'Parents'},
]
EMAIL_TYPES = [
    {'id': 'm-def', 'code': 'DEF', 'title': 'Default E-Mail'},
    {'id': 'm-sccc', 'code': 'SCCC', 'title': 'SCCC Email'},
    {'id': 'm-nye2', 'code': 'NYE2', 'title': 'Emer Alert - Secondary Email'},
    {'id': 'm-othr', 'code': 'OTHR', 'title': 'Other E-mail'},
]
ADDRESS_TYPES = [{'id': 'a-ma', 'code': 'MA', 'title': 'Mailing', 'type': 'mailing'}]
EMERGENCY_CONTACT_TYPES = [{'id': 'ect-emergency', 'title': 'emergency'}]

BY_ENDPOINT = {
    'races': RACES,
    'ethnicities': ETHNICITIES,
    'phone-types': PHONE_TYPES,
    'email-types': EMAIL_TYPES,
    'address-types': ADDRESS_TYPES,
    'emergency-contact-types': EMERGENCY_CONTACT_TYPES,
}


class _Client:
    """Stands in for Ethos: answers _api_request from BY_ENDPOINT."""
    URL = 'https://example.invalid'

    def __init__(self, respond=None):
        self.calls = []
        self.respond = respond

    def get_preferred_accept_header(self, _resource):
        return None

    def _api_request(self, method, url, message_type, description='', headers=None, **kwargs):
        self.calls.append(url)
        if self.respond:
            return self.respond(url), None
        endpoint = url.split('/api/')[1].split('?')[0]
        if 'offset=0&' not in url:
            return _Resp([]), None  # second page is empty, so paging stops
        return _Resp(BY_ENDPOINT[endpoint]), None


class FetchResourceTests(SimpleTestCase):
    def test_goes_through_api_request(self):
        client = _Client()
        records, error = reference.fetch_resource(client, 'races')
        self.assertIsNone(error)
        self.assertEqual(len(records), 5)
        self.assertEqual(len(client.calls), 1)

    def test_http_error_is_returned_not_raised(self):
        records, error = reference.fetch_resource(
            _Client(respond=lambda url: _Resp({'e': 1}, status=503)), 'races')
        self.assertEqual(records, [])
        self.assertIn('503', error)

    def test_timeout_is_returned_not_raised(self):
        def _boom(url):
            raise requests.Timeout('read timed out')
        records, error = reference.fetch_resource(_Client(respond=_boom), 'races')
        self.assertEqual(records, [])
        self.assertIn('Timeout', error)


class BuildGuidMapTests(SimpleTestCase):
    def test_races_keep_code_id_and_racial_category(self):
        guids, _ = build_guid_map(_Client())
        self.assertEqual(guids['races'][0], {'id': 'r-white', 'code': '1', 'title': 'White',
                                             'racial_category': 'white'})

    def test_ethnicities_split_on_reporting_category(self):
        guids, _ = build_guid_map(_Client())
        self.assertEqual((guids['hispanic'], guids['non_hispanic']), ('e-his', 'e-non'))

    def test_ethnicities_fall_back_to_titles(self):
        no_reporting = [{'id': 'e-non', 'title': 'Not Hispanic or Latino'},
                        {'id': 'e-his', 'title': 'Hispanic or Latino'}]

        def respond(url):
            if '/api/ethnicities' in url and 'offset=0&' in url:
                return _Resp(no_reporting)
            return _Resp([])
        guids, _ = build_guid_map(_Client(respond=respond), only={'ethnicities'})
        self.assertEqual((guids['hispanic'], guids['non_hispanic']), ('e-his', 'e-non'))

    def test_contact_types_resolve(self):
        guids, _ = build_guid_map(_Client())
        self.assertEqual(guids['phone_type'], 'p-ce')
        self.assertEqual(guids['home_phone_type'], 'p-pr')
        self.assertEqual(guids['parent_phone_type'], 'p-pa')
        self.assertEqual(guids['email_type'], 'm-def')
        self.assertEqual(guids['parent_email_type'], 'm-nye2')
        self.assertEqual(guids['address_type'], 'a-ma')
        self.assertEqual(guids['emergency_contact_type'], 'ect-emergency')

    def test_each_code_table_is_read_once(self):
        client = _Client()
        build_guid_map(client)
        self.assertEqual(len(client.calls), len(BY_ENDPOINT))

    def test_only_limits_the_resources_read(self):
        guids, report = build_guid_map(_Client(), only={'races'})
        self.assertEqual(set(guids), {'races'})
        self.assertEqual([e['resource'] for e in report], ['races'])

    def test_unmatched_single_reports_options(self):
        def respond(url):
            if '/api/address-types' in url and 'offset=0&' in url:
                return _Resp([{'id': 'x', 'code': 'BI', 'title': 'Billing'}])
            return _Resp([])
        guids, report = build_guid_map(_Client(respond=respond), only={'address_type'})
        self.assertEqual(guids, {})
        self.assertEqual(report[0]['status'], 'unmatched')
        self.assertEqual(report[0]['options'], ['BI'])

    def test_every_resource_declares_a_shape(self):
        for name, spec in RESOURCES.items():
            self.assertIn(spec['shape'], ('list', 'single', 'split'), name)
            self.assertTrue(spec['endpoint'], name)


class MergeAndLoadTests(SimpleTestCase):
    def test_merge(self):
        self.assertEqual(merge_guids({'a': 1}, {'b': 2}), ({'a': 1, 'b': 2}, ['b'], []))
        self.assertEqual(merge_guids({'a': 'mine'}, {'a': 'theirs'}), ({'a': 'mine'}, [], ['a']))
        self.assertEqual(merge_guids({'a': 'mine'}, {'a': 'theirs'}, overwrite=True)[0]['a'], 'theirs')
        self.assertEqual(merge_guids({'a': ''}, {'a': 'new'})[1], ['a'])
        self.assertEqual(merge_guids({'a': 'x'}, {'a': 'x'})[1:], ([], []))

    def test_load(self):
        self.assertEqual(load_guids_blob('{"a": 1}'), {'a': 1})
        self.assertEqual(load_guids_blob({'a': 1}), {'a': 1})
        self.assertEqual(load_guids_blob('{nope'), {})
        self.assertEqual(load_guids_blob(None), {})


@override_settings(MULTI_CAMPUS=False)
class PopulateSisGuidsCommandTests(TestCase):
    def _run(self, **opts):
        with patch(f'{PKG}.management.commands.populate_sis_guids.get_client',
                   return_value=_Client()):
            call_command('populate_sis_guids', stdout=open('/dev/null', 'w'), **opts)

    def _stored(self):
        setting = Setting.objects.filter(key=sis_settings.key).first()
        return load_guids_blob((setting.value or {}).get('guids')) if setting else {}

    def test_writes_the_resolved_keys(self):
        self._run()
        stored = self._stored()
        self.assertEqual(stored['hispanic'], 'e-his')
        self.assertEqual(stored['phone_type'], 'p-ce')
        self.assertEqual(len(stored['races']), 5)

    def test_dry_run_writes_nothing(self):
        self._run(dry_run=True)
        self.assertEqual(self._stored(), {})

    def test_preserves_unrelated_keys_and_fields(self):
        Setting.objects.update_or_create(key=sis_settings.key, defaults={'value': {
            'guids': json.dumps({'academic_level': {'id': 'keep-me'}}), 'other': 'x'}})
        self._run()
        self.assertEqual(self._stored()['academic_level'], {'id': 'keep-me'})
        self.assertEqual(Setting.objects.get(key=sis_settings.key).value['other'], 'x')

    def test_hand_set_key_is_kept_without_overwrite(self):
        Setting.objects.update_or_create(key=sis_settings.key, defaults={'value': {
            'guids': json.dumps({'phone_type': 'hand-set'})}})
        self._run()
        self.assertEqual(self._stored()['phone_type'], 'hand-set')
        self._run(overwrite=True)
        self.assertEqual(self._stored()['phone_type'], 'p-ce')

    def test_corrupt_blob_is_refused_not_replaced(self):
        Setting.objects.update_or_create(key=sis_settings.key, defaults={'value': {'guids': '{nope'}})
        with self.assertRaises(CommandError):
            self._run()
        self.assertEqual(Setting.objects.get(key=sis_settings.key).value['guids'], '{nope')

    def test_is_idempotent(self):
        self._run()
        first = self._stored()
        self._run()
        self.assertEqual(self._stored(), first)

    def test_unknown_resource_is_rejected(self):
        with self.assertRaises(CommandError):
            self._run(only='races,nope')

    def test_only_writes_the_named_resource(self):
        self._run(only='races')
        self.assertEqual(set(self._stored()), {'races'})

"""Ethos reference (code table) reads, and the SIS GUIDS map they produce.

The payload builders resolve every coded value (race, ethnicity, phone, email, address and
emergency-contact type) through the ``guids`` blob in the cis "SIS GUIDS" setting, and send
null for a key that is unset (package_ethos#3). This module reads the real values from Ethos
so ``populate_sis_guids`` can fill the blob.

Read-only: nothing here writes to Ethos or to the database. Ported from SCCC's tenant repo.
"""
import json
import logging
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

#: EEDM pages its code tables; this is the per-request page size.
PAGE_SIZE = 100

#: Safety valve so a misbehaving endpoint cannot page forever.
MAX_PAGES = 50

#: guids key (or group of keys) -> how to resolve it.
#: ``list`` stores [{id, code, title, racial_category}] because the builders match on code;
#: ``single`` picks one record by the first ``preferred`` code/title/type that matches;
#: ``split`` resolves several keys from one table by Ethos's reporting category.
RESOURCES = {
    'races': {
        'endpoint': 'races',
        'key': 'races',
        'shape': 'list',
    },
    'ethnicities': {
        'endpoint': 'ethnicities',
        'shape': 'split',
        # Ethos reports `reporting.country.ethnicCategory` as hispanic / nonHispanic;
        # titles are the fallback.
        'split_keys': {'hispanic': 'hispanic', 'non_hispanic': 'nonHispanic'},
    },
    'phone_type': {
        'endpoint': 'phone-types',
        'key': 'phone_type',
        'shape': 'single',
        'preferred': ['mobile', 'cell'],
    },
    'home_phone_type': {
        'endpoint': 'phone-types',
        'key': 'home_phone_type',
        'shape': 'single',
        # Banner instances title PR 'Home' or 'Residence'.
        'preferred': ['home', 'residence', 'pr'],
    },
    'parent_phone_type': {
        'endpoint': 'phone-types',
        'key': 'parent_phone_type',
        'shape': 'single',
        'preferred': ['parents', 'parent', 'pa'],
    },
    'email_type': {
        'endpoint': 'email-types',
        'key': 'email_type',
        'shape': 'single',
        # The payloads carry the student's own address, so a personal type, not the
        # college-issued account. DEF is Banner's general personal address.
        'preferred': ['personal', 'home', 'def', 'othr'],
    },
    'parent_email_type': {
        'endpoint': 'email-types',
        'key': 'parent_email_type',
        'shape': 'single',
        'preferred': ['parent', 'nye2', 'othr'],
    },
    'address_type': {
        'endpoint': 'address-types',
        'key': 'address_type',
        'shape': 'single',
        'preferred': ['home', 'mailing'],
    },
    'emergency_contact_type': {
        'endpoint': 'emergency-contact-types',
        'key': 'emergency_contact_type',
        'shape': 'single',
        'preferred': ['emergency'],
    },
}


def fetch_resource(client, endpoint, page_size=PAGE_SIZE):
    """GET every page of an Ethos code table.

    Returns ``(records, error)``. A failed request returns the error string with whatever
    pages were already read, so a partial table is visible rather than silently empty.
    Each request goes through ``_api_request``, so it carries the client timeout and is
    logged to EthosLog.
    """
    records = []
    message_type = f'reference_{endpoint.replace("-", "_")}'
    for page in range(MAX_PAGES):
        query = urlencode({'offset': page * page_size, 'limit': page_size})
        url = f'{client.URL}/api/{endpoint}?{query}'
        accept = client.get_preferred_accept_header(endpoint) or 'application/json'
        try:
            resp, _log = client._api_request(
                'GET', url, message_type, description='populate_sis_guids',
                headers={'Accept': accept})
        except requests.RequestException as e:
            return records, f'{type(e).__name__}: {e}'

        if not resp.ok:
            return records, f'HTTP {resp.status_code}: {(resp.text or "")[:200]}'

        try:
            batch = resp.json()
        except ValueError as e:
            return records, f'Response was not JSON: {e}'

        if not isinstance(batch, list):
            return records, f'Expected a list, got {type(batch).__name__}'

        records.extend(batch)
        if len(batch) < page_size:
            return records, None

    return records, f'Stopped after {MAX_PAGES} pages; the endpoint may not honour offset'


def _record_code(record):
    """The code Ethos uses for a record, however this resource spells it."""
    for field in ('code', 'title', 'abbreviation'):
        value = record.get(field)
        if value:
            return str(value)
    return ''


def _pick_preferred(records, preferred):
    """First record whose code, title or type matches ``preferred``, in that order."""
    for want in preferred:
        for record in records:
            candidates = {
                str(record.get('code') or '').lower(),
                str(record.get('title') or '').lower(),
                str(record.get('type') or '').lower(),
            }
            if want.lower() in candidates:
                return record
    return None


def _reporting_country(record):
    reporting = record.get('reporting')
    if isinstance(reporting, list) and reporting:
        reporting = reporting[0]
    if isinstance(reporting, dict):
        country = reporting.get('country')
        if isinstance(country, dict):
            return country
    return {}


def _racial_category(record):
    """Ellucian's stable race vocabulary, e.g. 'americanIndianOrAlaskaNative'.

    Kept beside the numeric code because codes are a local convention (SCCC numbers its
    races 1-6 in an order unrelated to its own option keys) while this vocabulary is not.
    """
    return _reporting_country(record).get('racialCategory')


def _ethnic_category(record):
    return _reporting_country(record).get('ethnicCategory')


def build_guid_map(client, only=None):
    """Read every configured resource and return ``(guids, report)``.

    ``guids`` holds only the keys that resolved. ``report`` has one entry per resource
    describing what happened, so the command can print it whether or not anything is
    written.
    """
    guids = {}
    report = []
    # Several resources share an endpoint (phone-types feeds three keys). Read each table
    # once: a refetch would only add duplicate EthosLog rows and latency.
    tables = {}

    for name, spec in RESOURCES.items():
        if only and name not in only:
            continue

        if spec['endpoint'] not in tables:
            tables[spec['endpoint']] = fetch_resource(client, spec['endpoint'])
        records, error = tables[spec['endpoint']]
        if error:
            report.append({'resource': name, 'status': 'error',
                           'detail': error, 'count': len(records)})
            continue

        if not records:
            report.append({'resource': name, 'status': 'empty',
                           'detail': 'endpoint returned no records', 'count': 0})
            continue

        if spec['shape'] == 'list':
            guids[spec['key']] = [
                {
                    'id': r.get('id'),
                    'code': _record_code(r),
                    'title': r.get('title'),
                    'racial_category': _racial_category(r),
                }
                for r in records if r.get('id')
            ]
            report.append({
                'resource': name, 'status': 'ok',
                'detail': f"{len(guids[spec['key']])} entries",
                'count': len(records),
                'options': [_record_code(r) for r in records],
            })

        elif spec['shape'] == 'single':
            chosen = _pick_preferred(records, spec['preferred'])
            if chosen is None:
                report.append({
                    'resource': name, 'status': 'unmatched',
                    'detail': f"none of {spec['preferred']} found; choose one manually",
                    'count': len(records),
                    'options': [_record_code(r) for r in records],
                })
                continue
            guids[spec['key']] = chosen.get('id')
            report.append({
                'resource': name, 'status': 'ok',
                'detail': f"{_record_code(chosen)} -> {chosen.get('id')}",
                'count': len(records),
                'options': [_record_code(r) for r in records],
            })

        elif spec['shape'] == 'split':
            resolved = {}
            for guid_key, category in spec['split_keys'].items():
                match = next((r for r in records if _ethnic_category(r) == category), None)
                if match is None:
                    # Not every Banner instance fills the reporting block: match on title.
                    is_non = guid_key == 'non_hispanic'
                    match = next(
                        (r for r in records
                         if 'hispanic' in str(r.get('title') or '').lower()
                         and is_non == ('not' in str(r.get('title') or '').lower()
                                        or 'non' in str(r.get('title') or '').lower())),
                        None)
                if match is not None:
                    resolved[guid_key] = match.get('id')

            guids.update(resolved)
            missing = set(spec['split_keys']) - set(resolved)
            report.append({
                'resource': name,
                'status': 'ok' if not missing else 'partial',
                'detail': (f"resolved {sorted(resolved)}"
                           + (f"; missing {sorted(missing)}" if missing else '')),
                'count': len(records),
                'options': [str(r.get('title') or '') for r in records],
            })

    return guids, report


def merge_guids(existing, fetched, overwrite=False):
    """Merge ``fetched`` into ``existing``; returns ``(merged, changed_keys, skipped_keys)``.

    Without ``overwrite`` a key that already holds a value is kept: a CE may have set a
    GUID by hand that the preferred-code guess would not pick.
    """
    merged = dict(existing)
    changed, skipped = [], []

    for key, value in fetched.items():
        if key in merged and merged[key] not in (None, '', [], {}):
            if merged[key] == value:
                continue
            if not overwrite:
                skipped.append(key)
                continue
        merged[key] = value
        changed.append(key)

    return merged, changed, skipped


def load_guids_blob(raw):
    """Parse the ``guids`` value of the SIS GUIDS setting, which stores it as text."""
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or '{}')
    except (TypeError, ValueError):
        logger.error('SIS GUIDS guids is not valid JSON; treating it as empty')
        return {}
    return parsed if isinstance(parsed, dict) else {}

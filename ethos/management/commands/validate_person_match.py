"""Check the person-matching payload for one student without sending it (package_ethos#3).

    python manage.py validate_person_match <student id>
    python manage.py validate_person_match <student id> --offline --show-payload

Banner rejects a person-matching request one error at a time, so a payload with three
problems takes three round trips, and the round trip that finally succeeds creates a
prospect record. This command applies the same rules locally and reports every failure at
once. Each rule records the Banner error it stands in for, so a report can be matched to
what Banner says. The rules were derived by probing SCCC's Ethos; see
``docs/person-matching-requests.md``.

Two things it cannot check, because Banner resolves them internally:

* the prospect's default degree (Banner's "Degree not found"); the schema has no degree,
  program or academic-level input;
* whether a region's ISO code is mapped in STVSTAT. Only the format (US-XX) is checked.

So a clean report means nothing in the payload is wrong, not that the request will succeed.

The payload is built by ``client.get_client()``, so a tenant that overrides ``studentJSON``
is checked on what it actually sends. Pass ``--campus <code>`` on a multi-campus deployment.
"""
import json
import re
import uuid
from datetime import date

from django.core.management.base import CommandError

from ...client import get_client
from ...command_base import EthosCommand
from ...reference import fetch_resource

#: guids key -> (Ethos code table, the Banner error a bad value produces).
CONTACT_TYPES = {
    'phone_type': ('phone-types', 'Phone type not found'),
    'email_type': ('email-types', 'Email type not found'),
    'address_type': ('address-types', 'Address type not found'),
}

#: Values Banner accepts for `gender`; anything else is
#: "Invalid enumeration value for [gender]".
GENDER_VALUES = {'male', 'female', 'unknown'}

#: Accepted `matchingCriteria.credential.type` values. Banner does not check the value.
CREDENTIAL_TYPES = {'ssn', 'sin', 'bannerId', 'colleaguePersonId', 'elevateId'}

REGION_RE = re.compile(r'^[A-Z]{2}-[A-Z0-9]{1,3}$')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class Check:
    """One rule, its outcome, and the Banner error it stands in for."""

    def __init__(self, name, ok, detail='', banner_error=None, warning=False):
        self.name = name
        self.ok = ok
        self.detail = detail
        self.banner_error = banner_error
        self.warning = warning


class Command(EthosCommand):
    help = 'Validate the person-matching payload for a student without sending it.'

    def add_arguments(self, parser):
        super().add_arguments(parser)  # --campus
        parser.add_argument('student_id', help='cis.Student id (a UUID)')
        parser.add_argument('--offline', action='store_true',
                            help='Skip the Ethos reads: the contact-type GUIDs are checked for '
                                 'presence, not existence.')
        parser.add_argument('--show-payload', action='store_true',
                            help='Print the payload that was checked.')

    def handle(self, *args, **options):
        student = self._get_student(options['student_id'])
        client = get_client()

        try:
            payload = json.loads(client.studentJSON(student))
        except Exception as exc:
            raise CommandError(f'Could not build the payload: {type(exc).__name__}: {exc}')

        checks = self.run_checks(payload, client, options['offline'])

        if options['show_payload']:
            self.stdout.write(json.dumps(payload, indent=2))
            self.stdout.write('')

        self._report(checks, student)

    def _get_student(self, raw):
        from cis.models import Student
        try:
            guid = uuid.UUID(str(raw))
        except (TypeError, ValueError):
            raise CommandError(f'{raw!r} is not a UUID.')
        try:
            return Student.objects.get(id=guid)
        except Student.DoesNotExist:
            raise CommandError(f'No student with id {guid}.')

    # -- rules ---------------------------------------------------------

    def run_checks(self, payload, client=None, offline=True):
        names = (payload.get('names') or {}).get('legal') or {}
        criteria = payload.get('matchingCriteria') or {}

        checks = [self._check_names(names), self._check_dob(criteria)]

        if 'gender' in payload:
            checks.append(self._check_gender(payload['gender']))
        if 'credential' in criteria:
            checks.append(self._check_credential(criteria['credential']))

        # The packaged studentJSON puts phone/email/address at the top level; some tenant
        # overrides nest them under matchingCriteria. Check whichever is present.
        blocks = {b: criteria.get(b) or payload.get(b) for b in ('phone', 'email', 'address')}

        tables = {} if offline else self._load_tables(client)
        for block, guid_key in (('phone', 'phone_type'), ('email', 'email_type'),
                                ('address', 'address_type')):
            if blocks[block]:
                checks.append(self._check_type(block, blocks[block], guid_key, tables, offline))

        if blocks['email']:
            checks.append(self._check_email_address(blocks['email']))
        if blocks['address']:
            checks.append(self._check_region(blocks['address']))

        checks.append(Check(
            'prospect default degree', True,
            'not checkable here: Banner resolves it internally and the schema has no '
            'degree input', warning=True))
        return checks

    def _check_names(self, names):
        missing = [f for f in ('firstName', 'lastName') if not names.get(f)]
        return Check(
            'legal first and last name', not missing,
            f'missing {", ".join(missing)}' if missing
            else f"{names.get('firstName')} {names.get('lastName')}",
            'Legal first name and last name are required')

    def _check_dob(self, criteria):
        raw = criteria.get('dateOfBirth')
        if not raw:
            return Check('date of birth', False, 'not set', 'Invalid date format [dateOfBirth]')
        try:
            parsed = date.fromisoformat(str(raw))
        except ValueError:
            return Check('date of birth', False, f'{raw!r} is not YYYY-MM-DD',
                         'Invalid date format [dateOfBirth]')
        if parsed > date.today():
            return Check('date of birth', False, f'{raw} is in the future',
                         'Date of Birth cannot be a future date')
        return Check('date of birth', True, str(raw))

    def _check_gender(self, value):
        ok = value in GENDER_VALUES
        return Check('gender', ok,
                     f'{value!r}' + ('' if ok else f' not in {sorted(GENDER_VALUES)}'),
                     'Invalid enumeration value for [gender]')

    def _check_credential(self, credential):
        kind = (credential or {}).get('type')
        return Check('credential type', kind in CREDENTIAL_TYPES, f'{kind!r}',
                     'Invalid enumeration value for [credential.type]')

    def _load_tables(self, client):
        """Each contact code table, read once: guids key -> (records, error)."""
        return {key: fetch_resource(client, endpoint)
                for key, (endpoint, _error) in CONTACT_TYPES.items()}

    def _check_type(self, block, body, guid_key, tables, offline):
        """The type GUID must be set and must exist in this tenant's code table."""
        _endpoint, banner_error = CONTACT_TYPES[guid_key]
        guid = ((body or {}).get('type') or {}).get('id')

        if not guid:
            return Check(f'{block} type', False,
                         f"SIS GUIDS guids['{guid_key}'] is not set, so the payload sends a "
                         f"null id (populate_sis_guids fills it)",
                         f'{block.title()} type is required')

        if offline:
            return Check(f'{block} type', True, f'{guid} (not verified)', banner_error,
                         warning=True)

        records, error = tables.get(guid_key, ([], 'not read'))
        if error:
            # A 403 on the code table is not evidence that the GUID is wrong.
            return Check(f'{block} type', True, f'{guid}: could not verify: {error}',
                         banner_error, warning=True)

        match = next((r for r in records if r.get('id') == guid), None)
        if match is None:
            return Check(f'{block} type', False, f"{guid} is not in this tenant's table",
                         banner_error)
        return Check(f'{block} type', True, f"{match.get('code')}: {match.get('title')}")

    def _check_email_address(self, email):
        address = (email or {}).get('address') or ''
        return Check('email address', bool(EMAIL_RE.match(address)), address or '(empty)',
                     "Email address should have at least one character in front of '@' "
                     "and at least one char after '@'")

    def _check_region(self, address):
        region = ((((address or {}).get('place') or {}).get('country') or {})
                  .get('region') or {}).get('code') or ''
        ok = bool(REGION_RE.match(region))
        detail = region or '(empty)'
        if ok:
            detail += ': well formed; only Banner knows the STVSTAT mapping'
        return Check('address region', ok, detail,
                     'ISO code mapping for the region does not exist in STVSTAT', warning=ok)

    # -- output --------------------------------------------------------

    def _report(self, checks, student):
        failures = [c for c in checks if not c.ok]

        for check in checks:
            if not check.ok:
                style, mark = self.style.ERROR, 'FAIL'
            elif check.warning:
                style, mark = self.style.WARNING, 'note'
            else:
                style, mark = self.style.SUCCESS, ' ok '
            self.stdout.write(style(f'  {mark}  {check.name:26} {check.detail}'))
            if not check.ok and check.banner_error:
                self.stdout.write(f'        Banner would say: "{check.banner_error}"')

        self.stdout.write('')
        if failures:
            self.stdout.write(self.style.ERROR(f'{len(failures)} problem(s) in the payload for {student}.'))
            return
        self.stdout.write(self.style.SUCCESS(f'Payload for {student} passes every rule checked locally.'))
        self.stdout.write('A Banner rejection now points at Banner configuration, most likely the '
                          'prospect default degree or an STVSTAT mapping.')

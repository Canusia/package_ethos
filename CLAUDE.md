# Ethos App (Git Submodule)

Ellucian Ethos SIS integration client for communicating with the university's Student Information System via the Ethos Integration API.

This package has a dual-layer structure for use as both a git submodule (development) and a pip-installed package (production).

## Structure

```
ethos/                           ← git submodule root (outer package)
├── __init__.py                  # Outer package init (empty)
├── setup.py, setup.cfg          # Package distribution config
├── MANIFEST.in, requirements.txt
├── README.md                    # Host app integration instructions
├── CLAUDE.md
├── tests/                       # Tests at outer level
│   ├── test_academic_periods.py
│   └── test_subjects.py
└── ethos/                       ← inner Django app
    ├── __init__.py
    ├── apps.py                  # EthosConfig (prod) + DevEthosConfig (dev)
    ├── models.py                # EthosLog, EthosApplication, EthosResource, EthosRepresentation, EthosMessage, EthosConsumeCursor
    ├── serializers.py           # DRF serializers for EthosResource, EthosLog, EthosMessage
    ├── settings/                # DB-backed configuration
    │   └── ethos_consume.py     # Operator settings: poll on/off, limit, batches, consume-after-poll, cron
    ├── consume/                 # Change-notification consume framework
    │   ├── adapter.py           # parse_notification() — the only place that knows Ethos's envelope field names
    │   ├── config.py            # getattr(settings, ...) accessors for the five ETHOS_CONSUME_* / ETHOS_LOG_RETENTION_DAYS keys
    │   ├── base.py               # ConsumeHandler protocol — plan()/apply(), Plan/Change/Result dataclasses
    │   ├── registry.py           # get_handler(resource_name) — resolves ETHOS_CONSUME_HANDLERS dotted paths
    │   ├── poller.py             # poll() — drains /consume into EthosMessage, advances EthosConsumeCursor atomically
    │   └── service.py            # consume_message() — dispatches one stored EthosMessage to its handler
    ├── tasks.py                 # django-tasks background task: import_sections_for_term
    ├── urls.py                  # All ethos URL patterns (app_name='ethos')
    ├── library/                 # All Ethos API client code
    │   ├── base.py              # EthosBase — auth, _api_request, get_preferred_accept_header
    │   ├── ethos.py             # Ethos class — composes all mixins
    │   ├── person.py            # PersonMixin — person CRUD, matching, credentials
    │   ├── academic.py          # AcademicMixin — admissions, programs, sites
    │   ├── academic_periods.py  # AcademicPeriodsMixin — period lookup/pagination
    │   ├── courses.py           # CoursesMixin — course list + by-id
    │   ├── subjects.py          # SubjectsMixin — subject list + by-id
    │   ├── section.py           # SectionMixin — get_sections() paginated
    │   ├── section_detail.py    # SectionDetailMixin — meeting times, instructors, enrollment, registrations
    │   ├── student_records.py   # StudentRecordsMixin — student record, programs, standings, registrations
    │   ├── student_account.py   # StudentAccountMixin — account summary/details, financial aid
    │   ├── grades.py            # GradesMixin — grade reads + final grade submission
    │   ├── holds.py             # HoldsMixin — list/get/release person holds
    │   ├── reference.py         # ReferenceMixin — academic levels, methods, schemes, catalogs, institutions
    │   ├── registration.py      # RegistrationMixin — section registrations, holds POST, mirroring (all writes return `(success, log)`)
    │   ├── payment.py           # PaymentMixin — fee assessment, FRL, student payments
    │   ├── admin.py             # AdminMixin — get_available_resources
    │   └── importer/            # Lazily re-exports SectionImporter from host app
    │       └── __init__.py      # Resolves SISImporter via cis.services.tenant_services (settings.TENANT_SERVICES_APP)
    ├── views/
    │   ├── academic_periods.py  # AcademicYear/Term import from Ethos
    │   ├── sections.py          # trigger_section_import, section_import_status (AJAX)
    │   ├── status.py            # API Explorer — status_page, run_method, METHOD_REGISTRY (44 methods)
    │   ├── resources.py         # EthosResource list/detail/sync views + DRF ViewSet
    │   ├── logs.py              # EthosLog list/detail views + DRF ViewSet
    │   ├── messages.py          # EthosMessage list/detail views + dry-run/consume actions + DRF ViewSet
    │   └── subjects.py          # Cohort/Subject import from Ethos
    ├── templates/ethos/
    │   ├── status.html          # API Explorer UI
    │   ├── resources/
    │   │   ├── index.html       # DataTables resource list with Active Header column
    │   │   ├── detail.html      # Full-page resource detail with Preferred column
    │   │   └── detail_partial.html  # Modal partial with Set/Clear AJAX buttons
    │   ├── logs/
    │   │   ├── index.html       # DataTables log list with auto-reload
    │   │   ├── detail.html      # Full-page log detail
    │   │   └── detail_partial.html  # Modal partial
    │   └── messages/
    │       ├── index.html       # DataTables message list (queue_id, resource, status, action)
    │       ├── detail.html      # Full-page message detail — raw payload + extracted envelope + consume result
    │       ├── detail_partial.html  # Modal partial
    │       └── _plan.html       # Renders a Plan (action/summary/changes) for dry-run and consume results
    └── management/commands/
        ├── import_subjects_from_ethos.py
        ├── import_terms_from_ethos.py
        ├── import_courses_from_ethos.py
        ├── import_sections_from_ethos.py
        ├── sync_ethos_resources.py
        ├── poll_ethos_messages.py       # GET/HEAD /consume -> stores EthosMessage rows; --peek, --from-id, --max-batches
        ├── process_ethos_messages.py    # Dispatches stored EthosMessage rows to handlers; --dry-run, --resource, --id, --force
        ├── purge_ethos_messages.py      # Deletes EthosMessage rows past ETHOS_CONSUME_RETENTION_DAYS
        └── purge_ethos_logs.py          # Deletes EthosLog rows past ETHOS_LOG_RETENTION_DAYS
```

## Host App Integration

See `README.md` for full integration steps. In brief, the host app (`myce/`) must:

1. Add the correct `INSTALLED_APPS` entry (see Dual App Configuration below)
2. Add ethos `staticfiles/` to `STATICFILES_DIRS` (DEBUG-conditional path)
3. Provide a `SISImporter` in the tenant-services app and set `settings.TENANT_SERVICES_APP` to it — this package resolves it via `cis.services.tenant_services.get_tenant_service('sis_importer')`
4. Include `path('ce/ethos/', include('ethos.ethos.urls'))` in `myce/urls.py`
5. Register term actions via `@term_actions.action(...)` in `ethos/views/sections.py`
6. Add the ethos SIS nav group to the CE menu in DB settings (see README)

## Dual App Configuration

- **Production** (pip-installed): `ethos.apps.EthosConfig` — app name `'ethos'`
- **Development** (submodule): `ethos.ethos.apps.DevEthosConfig` — app name `'ethos.ethos'`

Controlled by `DEBUG` in `settings.py`.

## Usage

Internal imports (within the package) use **relative imports**:
```python
from .base import EthosBase        # within library/
from ..library.ethos import Ethos  # from views/
```

External imports (from CIS or other apps) use **`find_spec`-based switching**:
```python
import importlib.util
if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
else:
    from ethos.library.ethos import Ethos
```

## Architecture

- **EthosBase** (`base.py`) provides JWT auth (cached with 30s buffer), `_api_request()` helper that logs all calls to `EthosLog`, `get_preferred_accept_header(resource_name)` for DB-driven Accept header selection, and GUID config loading from `sis_settings`.
- **Mixins** inherit from `EthosBase` and are composed into the `Ethos` class via multiple inheritance (MRO). 15 mixins total, 44 methods exposed in the API Explorer.
- **EthosLog** records every API call with method, URL, request headers/body, response status/body. Never stores the Authorization token. Exposes `response_json` (parsed `response_body` as dict, `{}` on parse failure) and `error_message` (best-effort short error string for failed calls) for callers that need structured response data — e.g. reading the new section-registration GUID from `mirror_registration` via `log.response_json.get('id')`.
- **EthosResource / EthosRepresentation** cache the available API resources from `/admin/available-resources`. Each resource can have a `preferred_representation` FK that overrides the hardcoded Accept header at call time.

## Accept Header Preference

Every mixin method that sends an Accept header calls:
```python
accept = self.get_preferred_accept_header('resource-name') or 'application/vnd.hedtech.integration.vN+json'
```

The preferred header is set per-resource from the UI at `/ce/ethos/resources/<pk>/`.

## API Base URL

`https://integrate.elluciancloud.com`

Auth token is a JWT obtained via `POST /auth` with the `COLLEAGUE_AUTH_CODE` from Django settings.

## Cross-App Dependencies

This app depends on `cis` for:
- `cis.services.tenant_services.get_tenant_service` — resolves the tenant-provided `SISImporter` (settings-indirected)
- `cis.settings.sis_settings` — GUID configuration
- `cis.utils.active_term` — current term lookup
- `cis.validators.validate_ssn` — SSN validation
- `cis.menu.draw_menu` / `cis.menu.cis_menu` — sidebar menu rendering

## Models & Migrations

Migrations live at `ethos/ethos/migrations/`. App label is `ethos` in both dev and prod modes.

| Migration | What it creates |
|-----------|----------------|
| `0001_initial.py` | EthosApplication, EthosResource, EthosRepresentation |
| `0002_ethoslog.py` | EthosLog |
| `0003_resource_preferred_representation.py` | preferred_representation FK on EthosResource |
| `0004_ethosconsumecursor_ethosmessage.py` | EthosMessage, EthosConsumeCursor |
| `0005_menu_ethos_messages.py` | Data migration — adds the "Messages" sub-item to the CE sidebar's SIS nav group in the `cis.settings.menu` Setting. Depends on `('cis', '__first__')`. Idempotent, reversible, no-ops when the Setting row or the `ethos` group is absent. |

### EthosMessage / EthosConsumeCursor

`EthosMessage` is one stored Ethos change-notification plus its consume result
(single, overwritten on re-run — not a history log). Envelope fields
(`queue_id`, `published_on`, `resource_name`, `resource_id`,
`resource_version`, `operation`, `content_type`, `message_type`,
`sis_message_id`, `initiated_on`, `publisher_id`) are extracted by
`consume/adapter.py`; `payload` holds the notification verbatim so nothing is
lost even if extraction is wrong. `status` is one of `pending`, `consumed`,
`failed`, `skipped`, `flagged`. `queue_id` is intentionally **not**
`unique=True` at the DB layer — see "Queue-id monotonicity" below.

`EthosConsumeCursor` is a one-row singleton (`.load()` gets-or-creates it)
holding `last_processed_id` and `last_polled_at`. It is a real table rather
than `MAX(queue_id)` over `EthosMessage` because retention purges delete rows;
a cursor derived from a purged table would replay the whole retention window
after the first purge.

### Two tiers of consume configuration

**Operator-tunable** — the `ethos.settings.ethos_consume` Setting, edited at
`/ce/settings/` ("Ethos Change Notifications"): `is_active` (the master poll
switch), `limit` (1-1000 per request), `max_batches` (requests per run),
`consume_after_poll`, and `cron`. Saving it upserts the `CronTab` row for
`poll_ethos_messages`, so the schedule is a setting field. `install()` seeds
both the row and the cron, with `is_active = No` — installing the release
changes no behavior until someone switches it on.

**Deployment-level** — `ETHOS_CONSUME_RETENTION_DAYS`, `ETHOS_LOG_RETENTION_DAYS`,
`ETHOS_CONSUME_AUTO`, `ETHOS_CONSUME_HANDLERS`, read from Django settings
(fed by `SECRETS`). These stay out of the web form deliberately: retention
governs data destruction, and the auto-consume map plus handler registry decide
what mutates student records.

`consume/config.py` is the seam. The Setting wins when it holds a usable value;
an out-of-range or non-numeric value counts as *unconfigured* and falls through
to the Django-settings key, so a bad form value degrades to the default rather
than breaking the poller.

Note the Setting's `key` is the stable literal `'ethos.settings.ethos_consume'`,
not `str(__name__)`. This package runs under two import roots, so a `__name__`-
derived key would point at a different Setting row in pip-installed vs submodule
mode and orphan the operator's configuration on the move between them. The
`CONFIGURATORS` `'app'` key does differ per config (`ethos` vs `ethos.ethos`) —
that one has to.

### Scheduling and CronLog

`poll_ethos_messages` is the only scheduled command. Its `CronTab` row is seeded by
`install()` and re-pointed whenever the setting is saved, so the schedule is edited
from the settings UI, never by hand.

When run with `-t/--time` (how `cis.management.commands.cron_jobs` invokes scheduled
commands) it emits `cron_task_started` / `cron_task_done` from `cis.signals.crontab`,
so each run appears in CronLog with a summary and a JSON detail blob. Two deliberate
behaviours: a **disabled** run still emits `done` recording "skipped: polling disabled"
(a silent no-op is indistinguishable from a broken cron), and a **failed** run emits
`done` with the error *before* re-raising — Ethos's pointer may already have advanced
past notifications the run failed to store, so that entry is part of the audit trail
for what was lost. Manual runs and `--peek` emit nothing.

Nothing else is scheduled: `process_ethos_messages` runs only when chained from a poll,
and both purge commands are manual.

### Queue-id monotonicity (open question)

Whether Ethos's `id` continues upward across a fully-drained-then-refilled
queue, or restarts, was not yet confirmed against a real tenant queue at the
time this was written (see the plan's "Verification Against Reality" section).
`poller.py` currently assumes upward-only ids and checks duplicates with
`exists()`-then-`create()` rather than `get_or_create()`. If ids are confirmed
to continue upward, add `unique=True` on `queue_id` in a follow-up migration.
If they are found to restart, do **not** — `get_or_create(queue_id=...)` would
then silently drop new messages after a restart, and the dedupe key would need
to change to `(resource_id, published_on)` with a cursor that tolerates reset.

## Institution-Specific Importers

Section import logic lives in the **host app's tenant-services app** (e.g. `myce_tenant_configs/services/sis_importer.py`) as `SISImporter`, pointed to by `settings.TENANT_SERVICES_APP`. The `library/importer/__init__.py` lazily re-exports it via a module-level `__getattr__` so this package never imports a tenant-specific app at module-load time:

```python
from cis.services.tenant_services import get_tenant_service
SISImporter = get_tenant_service('sis_importer').SISImporter
```

`SISImporter` is responsible for:
- Looking up courses by `external_sis_id` before `get_or_create`
- Fetching full course details from the Ethos API on creation
- Saving course `external_sis_id`, `credit_hours`, and `meta` (raw Ethos JSON)

The `EXTERNAL_SIS_IMPORTER` setting is **no longer used**.

## Background Tasks

`tasks.py` defines `import_sections_for_term(term_id)` as a `django-tasks` `@task`. It:
1. Resolves the Ethos period ID from `term.external_sis_id` (or falls back to `get_academic_period_id(term.code)`)
2. Fetches raw sections via `Ethos().get_sections(period_id=...)`
3. Runs `SectionImporter().import_sections(raw_sections, term=term)`
4. Returns a counts dict

Run the worker:
```bash
docker exec django_web_ewu python /app/webapp/manage.py db_worker
```

## Management Commands

| Command | Description |
|---|---|
| `import_subjects_from_ethos` | Sync subjects/cohorts from Ethos |
| `import_terms_from_ethos` | Sync academic periods/terms from Ethos |
| `import_courses_from_ethos` | Sync courses from Ethos (`--create` to write to DB) |
| `import_sections_from_ethos` | Sync sections for a term from Ethos |
| `sync_ethos_resources` | Sync available API resources from `/admin/available-resources` |
| `poll_ethos_messages` | Store notifications off `/consume` into `EthosMessage`; never consumes (unless "Consume After Polling" is on, when it chains to `process_ethos_messages`). This is the command the `CronTab` row runs. Gated on the `is_active` setting — `--force` for a one-off while off; `--peek` (HEAD, no side effects) works while off too. Also `--limit`, `--max-batches`, `--from-id` (replay), `-t/--time` (supplied by `cron_jobs`; triggers the CronLog signals) |
| `process_ethos_messages` | Dispatch stored `EthosMessage` rows to their configured handler; never polls. `--dry-run` (plan only, writes nothing), `--resource`, `--id`, `--force`, `--limit` |
| `purge_ethos_messages` | Delete `EthosMessage` rows past `ETHOS_CONSUME_RETENTION_DAYS` (default 30). `--dry-run`, `--days` |
| `purge_ethos_logs` | Delete `EthosLog` rows past `ETHOS_LOG_RETENTION_DAYS` (default 90). `--dry-run`, `--days`. **Not scheduled** — nothing purged `EthosLog` before this command existed; the `cis` hourly cron's `purge_sis_logs`/`purge_sis_messages` only touch the legacy `SIS_Log`/`SIS_Subscription` models. |

## Change-Notification Consume Framework

See `README.md`'s "Change Notifications" section for the command reference,
settings table, and the `GET /consume` queue-pointer operational note. In
brief: `poll_ethos_messages` (capture, via `consume/poller.py`) and
`process_ethos_messages` (dispatch, via `consume/service.py`) are independent
— polling never consumes and consuming never talks to Ethos. A handler is a
`consume.base.ConsumeHandler` subclass implementing `plan()` (pure) and
`apply()` (writes), registered per resource name in the
`ETHOS_CONSUME_HANDLERS` setting and resolved by `consume/registry.py`. With
no handler configured for a resource, `process_ethos_messages` marks its
messages `skipped` and they stay that way — that is Part 1's intended end
state; Part 2 (a separate, later change) supplies the first real handler
(`section-registrations`) and turns it on via `ETHOS_CONSUME_AUTO`.

Nothing here is scheduled — no `CronTab` row, no `cron_jobs.py` edit. All four
commands are run manually until the pipeline is trusted per tenant.

### import_sections_from_ethos

Requires the term to already exist in the DB (matched by `external_sis_id` or `code`). Sections are always linked to that term.

```bash
# Dry run (prints what would be created)
python manage.py import_sections_from_ethos 202620

# Write to database
python manage.py import_sections_from_ethos 202620 --create

# Pass academic period GUID directly
python manage.py import_sections_from_ethos 0840696f-a9c4-46d9-acbc-1e335c240155 --create

# Export to CSV (works with or without --create)
python manage.py import_sections_from_ethos 202620 --csv /tmp/sections.csv

# Skip TeacherCourseCertificate creation
python manage.py import_sections_from_ethos 202620 --create --no-certificates
```

The CSV export includes columns: `id`, `course_name`, `highschool`, `section_number`, `class_number`, `term_name`, `term_code`, `instructor_name`, `instructor_email`, plus status flags `term_status`, `course_status`, `highschool_status`, `teacher_status`.

### section.py — SectionMixin notes

- `get_sections(term_code=None, period_id=None)` — returns raw Ethos section dicts; pass `period_id` to skip the term code lookup

## RegistrationMixin return contract

All write methods on `RegistrationMixin` (`update_registration_status`, `update_registration`, `mirror_registration`, `mirror_linked_registrations`) return a uniform `(success: bool, log: EthosLog)` 2-tuple. Callers that need response data (registration GUID, status string, error detail) read it off the log via `log.response_json` / `log.error_message` rather than positional return values.

`mirror_linked_registrations` returns `False` if the response carries `failedRegistrations`, or any registration entry has `failureReasons` or `statusIndicator == 'F'`, or the JSON fails to parse.

## Technical Debt

`registration.py` — `update_registration_status`, `update_registration`, `mirror_registration`, and `mirror_linked_registrations` bypass `_api_request` and call `requests` directly, manually creating `EthosLog` entries. These should be refactored to use `_api_request` for consistency.

## Running Tests

```bash
docker exec -w /app/webapp django_web_ewu python manage.py test ethos.ethos
```

This is the inner Django app's suite (`ethos/tests/`, including the consume
framework tests in `test_consume_*.py`) — the one to run for regression
checks on this package.

The root-level `ethos.tests` package (`tests/` at the submodule root) exists
alongside it but as of this writing has 25 pre-existing failures (5 failures +
20 errors) from a missing tenant importer module
(`ethos.ethos.library.importer.ewu`) unrelated to any single change — do not
treat a run of the bare `ethos.tests` label as a regression signal without
first confirming which failures are pre-existing.

Tests mock `_api_request` to avoid real API calls.

## Docs in this package

| File | Audience | Purpose |
|------|----------|---------|
| `README.md` | Implementers | Install, settings wiring, menu, host integration steps |
| `docs/polling-change-notifications.md` | Operators / implementers | How the poll works end to end: the scheduled run, turning it on, command and config reference, message lifecycle, CronLog behaviour, troubleshooting |
| `docs/ethos-change-notifications.md` | Implementers | The verified wire-level `/consume` contract — endpoint, envelope fields, drain semantics |
| `docs/samples/` | Tests + reference | 27 real CTC notifications, doubling as the test fixture at `ethos/tests/fixtures/` |

When changing the poll, the scheduler, or the operator settings, update
`docs/polling-change-notifications.md` in the same commit — it is the doc an
implementer at another tenant will read first.

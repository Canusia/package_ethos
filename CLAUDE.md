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
    ├── models.py                # EthosLog, EthosApplication, EthosResource, EthosRepresentation
    ├── serializers.py           # DRF serializers for EthosResource and EthosLog
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
    │   ├── registration.py      # RegistrationMixin — section registrations, holds POST, mirroring
    │   ├── payment.py           # PaymentMixin — fee assessment, FRL, student payments
    │   ├── admin.py             # AdminMixin — get_available_resources
    │   └── importer/            # Re-exports SectionImporter from host app
    │       └── __init__.py      # Imports SectionImporter from cis.services.sis_importer
    ├── views/
    │   ├── academic_periods.py  # AcademicYear/Term import from Ethos
    │   ├── sections.py          # trigger_section_import, section_import_status (AJAX)
    │   ├── status.py            # API Explorer — status_page, run_method, METHOD_REGISTRY (44 methods)
    │   ├── resources.py         # EthosResource list/detail/sync views + DRF ViewSet
    │   └── logs.py              # EthosLog list/detail views + DRF ViewSet
    │   └── subjects.py          # Cohort/Subject import from Ethos
    ├── templates/ethos/
    │   ├── status.html          # API Explorer UI
    │   ├── resources/
    │   │   ├── index.html       # DataTables resource list with Active Header column
    │   │   ├── detail.html      # Full-page resource detail with Preferred column
    │   │   └── detail_partial.html  # Modal partial with Set/Clear AJAX buttons
    │   └── logs/
    │       ├── index.html       # DataTables log list with auto-reload
    │       ├── detail.html      # Full-page log detail
    │       └── detail_partial.html  # Modal partial
    └── management/commands/
        ├── import_subjects_from_ethos.py
        ├── import_terms_from_ethos.py
        ├── import_courses_from_ethos.py
        ├── import_sections_from_ethos.py
        └── sync_ethos_resources.py
```

## Host App Integration

See `README.md` for full integration steps. In brief, the host app (`myce/`) must:

1. Add the correct `INSTALLED_APPS` entry (see Dual App Configuration below)
2. Add ethos `staticfiles/` to `STATICFILES_DIRS` (DEBUG-conditional path)
3. Implement `cis.services.sis_importer.SISImporter` — the section importer used by this package
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
- **EthosLog** records every API call with method, URL, request headers/body, response status/body. Never stores the Authorization token.
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

## Institution-Specific Importers

Section import logic lives in the **host app** at `cis/services/sis_importer.py` as `SISImporter`. The `library/importer/__init__.py` simply re-exports it:

```python
from cis.services.sis_importer import SISImporter as SectionImporter
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

## Technical Debt

`registration.py` — `update_registration_status`, `update_registration`, `mirror_registration`, and `mirror_linked_registrations` bypass `_api_request` and call `requests` directly, manually creating `EthosLog` entries. These should be refactored to use `_api_request` for consistency.

## Running Tests

```bash
docker exec django_web_ewu python webapp/manage.py test ethos.tests
```

Tests mock `_api_request` to avoid real API calls.

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
    ├── tasks.py                 # django-tasks background task: import_sections_for_term
    ├── urls.py                  # All ethos URL patterns (app_name='ethos')
    ├── library/                 # All Ethos API client code
    │   ├── base.py              # EthosBase — auth, _api_request, GUID loading
    │   ├── ethos.py             # Ethos class — composes all mixins
    │   ├── person.py            # PersonMixin
    │   ├── academic.py          # AcademicMixin — get_sites, get_academic_programs
    │   ├── academic_periods.py  # AcademicPeriodsMixin
    │   ├── courses.py           # CoursesMixin
    │   ├── subjects.py          # SubjectsMixin
    │   ├── registration.py      # RegistrationMixin
    │   ├── payment.py           # PaymentMixin
    │   ├── section.py           # SectionMixin — get_sections()
    │   └── importer/            # Institution-specific section importers
    │       ├── __init__.py      # Reads EXTERNAL_SIS_IMPORTER from settings, exports SectionImporter
    │       └── ewu/
    │           └── section_import.py  # EWU SectionImporter
    ├── views/
    │   ├── academic_periods.py  # AcademicYear/Term import from Ethos
    │   ├── sections.py          # trigger_section_import, section_import_status (AJAX)
    │   ├── status.py            # API Explorer — status_page, run_method, METHOD_REGISTRY
    │   └── subjects.py          # Cohort/Subject import from Ethos
    ├── templates/ethos/
    │   └── status.html          # API Explorer UI
    └── management/commands/
        ├── import_subjects_from_ethos.py
        ├── import_terms_from_ethos.py
        ├── import_courses_from_ethos.py
        └── import_sections_from_ethos.py
```

## Host App Integration

See `README.md` for full integration steps. In brief, the host app (`myce/`) must:

1. Add the correct `INSTALLED_APPS` entry (see Dual App Configuration below)
2. Add ethos `staticfiles/` to `STATICFILES_DIRS` (DEBUG-conditional path)
3. Set `EXTERNAL_SIS_IMPORTER = '<institution>'` in `settings.py`
4. Include `path('ce/ethos/', include('ethos.ethos.urls'))` in `myce/urls.py`
5. Create component registry files in `myce/component_registry/` with `_prefix`-based handler paths (see README)

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

- **EthosBase** (`base.py`) provides JWT auth (cached with 30s buffer), `_api_request()` helper that logs all calls to `SIS_Log`, and GUID config loading from `sis_settings`.
- **Mixins** inherit from `EthosBase` and are composed into the `Ethos` class via multiple inheritance (MRO).

## API Base URL

`https://integrate.elluciancloud.com`

Auth token is a JWT obtained via `POST /auth` with the `COLLEAGUE_AUTH_CODE` from Django settings.

## Cross-App Dependencies

This app depends on `cis` for:
- `cis.models.sis.SIS_Log` — API call logging
- `cis.settings.sis_settings` — GUID configuration
- `cis.utils.active_term` — current term lookup
- `cis.validators.validate_ssn` — SSN validation

## Institution-Specific Importers

Section import logic is institution-specific and lives under `library/importer/`. The active importer is selected by `EXTERNAL_SIS_IMPORTER` in `myce/settings.py`:

```python
# myce/settings.py
EXTERNAL_SIS_IMPORTER = 'ewu'
```

`library/importer/__init__.py` reads this setting and dynamically exports `SectionImporter`. To add a new institution, create `library/importer/<institution>/section_import.py` with a `SectionImporter` class and update the setting.

All callers import from the package root:
```python
from ethos.ethos.library.importer import SectionImporter
```

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

## Running Tests

```bash
docker exec django_web_ewu python webapp/manage.py test ethos.tests
```

Tests mock `_api_request` to avoid real API calls.

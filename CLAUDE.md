# Ethos App (Git Submodule)

Ellucian Ethos SIS integration client for communicating with the university's Student Information System via the Ethos Integration API.

This package has a dual-layer structure for use as both a git submodule (development) and a pip-installed package (production).

## Structure

```
ethos/                           ← git submodule root (outer package)
├── __init__.py                  # Outer package init (empty)
├── setup.py, setup.cfg          # Package distribution config
├── MANIFEST.in, requirements.txt
├── CLAUDE.md
├── tests/                       # Tests at outer level
│   ├── test_academic_periods.py
│   └── test_subjects.py
└── ethos/                       ← inner Django app
    ├── __init__.py
    ├── apps.py                  # EthosConfig (prod) + DevEthosConfig (dev)
    ├── library/                 # All Ethos API client code
    │   ├── base.py              # EthosBase — auth, _api_request, GUID loading
    │   ├── ethos.py             # Ethos class — composes all mixins
    │   ├── person.py            # PersonMixin
    │   ├── academic.py          # AcademicMixin
    │   ├── academic_periods.py  # AcademicPeriodsMixin
    │   ├── courses.py           # CoursesMixin
    │   ├── subjects.py          # SubjectsMixin
    │   ├── registration.py      # RegistrationMixin
    │   ├── payment.py           # PaymentMixin
    │   └── section.py           # SectionMixin
    ├── views/
    │   ├── academic_periods.py  # AcademicYear/Term import from Ethos
    │   └── subjects.py          # Cohort/Subject import from Ethos
    └── management/commands/
        ├── import_subjects_from_ethos.py
        ├── import_terms_from_ethos.py
        └── import_courses_from_ethos.py
```

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

External imports (from CIS or other apps) use **DEBUG-based switching**:
```python
from django.conf import settings
if getattr(settings, 'DEBUG', False):
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

## Running Tests

```bash
docker exec django_web_ewu python webapp/manage.py test ethos.tests
```

Tests mock `_api_request` to avoid real API calls.

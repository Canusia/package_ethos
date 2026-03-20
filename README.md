# ethos

Ellucian Ethos SIS integration client for MyCE. Provides API access to the Ethos Integration platform and institution-specific importers for syncing SIS data into the CIS database.

## Overview

This package is designed for use as both a **git submodule** (development) and a **pip-installed package** (production). It exposes:

- An `Ethos` API client composed from mixins (academic periods, sections, courses, persons, etc.)
- Institution-specific section importers under `library/importer/`
- Django management commands for CLI-based SIS imports
- A background task (`import_sections_for_term`) for UI-triggered imports via django-tasks
- AJAX views for triggering and polling section imports from the term detail page
- An API Explorer page at `/ce/ethos/status` for interactively calling read-only Ethos methods

## Requirements

- Django 5.2+
- `django-tasks` with `DatabaseBackend`
- Access to the Ellucian Ethos Integration API (`COLLEAGUE_AUTH_CODE` in Django settings)

## Installation

### As a git submodule (development)

```bash
git submodule add <repo-url> webapp/ethos
```

### As a pip package (production)

```
ethos @ git+https://github.com/Canusia/package_ethos.git
```

---

## Host App Integration Steps

The following changes are required in the host Django project after adding this package.

### 1. INSTALLED_APPS

```python
import importlib.util
if importlib.util.find_spec('ethos.ethos'):
    INSTALLED_APPS += ['ethos.ethos.apps.DevEthosConfig']
else:
    INSTALLED_APPS += ['ethos.apps.EthosConfig']
```

### 2. Static Files (`settings.py`)

Add the ethos staticfiles directory to `STATICFILES_DIRS`. The path differs by install mode:

```python
if DEBUG:
    STATICFILES_DIRS += [
        os.path.join(get_package_path("ethos.ethos"), 'staticfiles') if get_package_path("ethos") else None
    ]
else:
    STATICFILES_DIRS += [
        os.path.join(get_package_path("ethos"), 'staticfiles') if get_package_path("ethos.ethos") else None
    ]
```

### 3. Institution Importer Constant (`settings.py`)

```python
# Selects the institution-specific section importer under ethos/library/importer/
EXTERNAL_SIS_IMPORTER = 'ewu'
```

Replace `'ewu'` with your institution's importer slug.

### 4. URLs (`myce/urls.py`)

Include the ethos URL conf under the CE prefix:

```python
import importlib.util
path('ce/ethos/', include('ethos.ethos.urls' if importlib.util.find_spec('ethos.ethos') else 'ethos.urls')),
```

This registers:

| URL | Name | Description |
|---|---|---|
| `ce/ethos/status/` | `ethos:ethos_status` | API Explorer page |
| `ce/ethos/status/run/` | `ethos:ethos_run_method` | API Explorer POST endpoint |
| `ce/ethos/academic_periods/lookup/` | `ethos:lookup_academic_period` | Look up period from SIS |
| `ce/ethos/academic_periods/create_from_sis/` | `ethos:academic_year_create_from_sis` | Create academic year from SIS |
| `ce/ethos/sections/import/` | `ethos:ethos_section_import` | Trigger section import |
| `ce/ethos/sections/import/status/` | `ethos:ethos_section_import_status` | Poll import status |

### 5. Component Registry

Create per-model component registry files that map action slugs to ethos view handlers. Use `find_spec` to select the correct module path:

```python
import importlib.util
_prefix = 'ethos.ethos' if importlib.util.find_spec('ethos.ethos') else 'ethos'
```

**`myce/component_registry/academic_year.py`**
```python
'lookup_guid':            f'{_prefix}.views.academic_periods.lookup_guid'
'lookup_academic_period': f'{_prefix}.views.academic_periods.lookup_academic_period'
'create_from_sis':        f'{_prefix}.views.academic_periods.create_from_sis'
```

**`myce/component_registry/term.py`**
```python
'pull_sections': f'{_prefix}.views.sections.trigger_section_import'
```

**`myce/component_registry/cohort.py`**
```python
'lookup_subjects': f'{_prefix}.views.subjects.lookup_subjects'
'create_from_sis': f'{_prefix}.views.subjects.create_from_sis'
```

---

## Adding a New Institution

1. Create `ethos/library/importer/<institution>/section_import.py` with a `SectionImporter` class implementing `import_sections(raw_sections, term, skip_certificates=False) -> dict`
2. Set `EXTERNAL_SIS_IMPORTER = '<institution>'` in `myce/settings.py`

## Configuration

| Setting | Description |
|---|---|
| `COLLEAGUE_AUTH_CODE` | Ethos API auth code from Secrets Manager |
| `EXTERNAL_SIS_IMPORTER` | Institution slug for section importer |

## Management Commands

```bash
python manage.py import_subjects_from_ethos
python manage.py import_terms_from_ethos <year_code>
python manage.py import_courses_from_ethos <term_code>
python manage.py import_sections_from_ethos <term_code> --create
```

## Background Task Worker

```bash
docker exec django_web_ewu python /app/webapp/manage.py db_worker
```

## UI Integration

- The term detail page (`/ce/term/<id>`) has a "Pull Sections from SIS" action that enqueues `import_sections_for_term` and polls for completion.
- The academic year add page (`/ce/academic_year/add_new`) has a "Import from SIS" flow for looking up and creating periods from Ethos.
- The API Explorer at `/ce/ethos/status` allows admins to call read-only Ethos methods interactively with optional `offset`/`limit` slicing.

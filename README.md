# ethos

Ellucian Ethos SIS integration client for MyCE. Provides API access to the Ethos Integration platform and institution-specific importers for syncing SIS data into the CIS database.

## Overview

This package is designed for use as both a **git submodule** (development) and a **pip-installed package** (production). It exposes:

- An `Ethos` API client composed from mixins (academic periods, sections, courses, persons, etc.)
- Institution-specific section importers under `library/importer/`
- Django management commands for CLI-based SIS imports
- A background task (`import_sections_for_term`) for UI-triggered imports via django-tasks
- AJAX views for triggering and polling section imports from the term detail page

## Requirements

- Django 5.2+
- `django-tasks` with `DatabaseBackend`
- Access to the Ellucian Ethos Integration API (`COLLEAGUE_AUTH_CODE` in Django settings)

## Installation

### As a git submodule (development)

```bash
git submodule add <repo-url> webapp/ethos
```

Add to `INSTALLED_APPS`:
```python
'ethos.ethos.apps.DevEthosConfig',
```

### As a pip package (production)

```
ethos @ git+https://github.com/Canusia/package_ethos.git
```

Add to `INSTALLED_APPS`:
```python
'ethos.apps.EthosConfig',
```

## Configuration

In `myce/settings.py`:

```python
# Selects the institution-specific section importer
EXTERNAL_SIS_IMPORTER = 'ewu'
```

## Adding a New Institution

1. Create `ethos/library/importer/<institution>/section_import.py` with a `SectionImporter` class implementing `import_sections(raw_sections, term, skip_certificates=False) -> dict`
2. Set `EXTERNAL_SIS_IMPORTER = '<institution>'` in `myce/settings.py`

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

The term detail page (`/ce/term/<id>`) has a "Pull Sections from SIS" action that enqueues `import_sections_for_term` and polls for completion via SweetAlert.

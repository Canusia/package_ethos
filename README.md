# ethos

Ellucian Ethos SIS integration client for MyCE. Provides API access to the Ethos Integration platform and institution-specific importers for syncing SIS data into the CIS database.

## Overview

This package is designed for use as both a **git submodule** (development) and a **pip-installed package** (production). It exposes:

- An `Ethos` API client composed from 15 mixins (persons, academic, sections, courses, grades, holds, financial, reference data, etc.)
- Structured API call logging via `EthosLog` model (replaces generic `SIS_Log`)
- A resource cache (`EthosResource` / `EthosRepresentation`) synced from `/admin/available-resources` with per-resource Accept header preferences
- A section importer adapter (`library/importer/`) that delegates to the host app's `cis.services.sis_importer.SISImporter`
- Django management commands for CLI-based SIS imports
- A background task (`import_sections_for_term`) for UI-triggered imports via django-tasks
- AJAX views for triggering and polling section imports from the term detail page
- An API Explorer page at `/ce/ethos/status` for interactively calling Ethos methods (44 methods across 13 groups)
- A resource browser at `/ce/ethos/resources` with DataTables, modal details, and preferred Accept header selection
- An API log viewer at `/ce/ethos/logs` with DataTables and modal log details

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

### 3. Section Importer (`cis/services/sis_importer.py`)

Implement a `SISImporter` class in the host app. This package imports it directly:

```python
from cis.services.sis_importer import SISImporter as SectionImporter
```

`SISImporter` must implement `import_sections(raw_sections, term, skip_certificates=False) -> dict`.

The `EXTERNAL_SIS_IMPORTER` settings constant is **no longer used**.

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
| `ce/ethos/resources/` | `ethos:ethos_resources` | Resource browser (DataTables) |
| `ce/ethos/resources/sync/` | `ethos:ethos_resources_sync` | Trigger resource sync from API |
| `ce/ethos/resources/<pk>/` | `ethos:ethos_resource_detail` | Resource detail page |
| `ce/ethos/resources/<pk>/set-preferred/` | `ethos:ethos_resource_set_preferred` | Set preferred Accept header |
| `ce/ethos/logs/` | `ethos:ethos_logs` | API log list (DataTables) |
| `ce/ethos/logs/<pk>/` | `ethos:ethos_log_detail` | Log detail |
| `ce/ethos/api/ethos-resource/` | — | DRF endpoint for resource DataTables |
| `ce/ethos/api/ethos-log/` | — | DRF endpoint for log DataTables |
| `ce/ethos/academic_periods/lookup/` | `ethos:lookup_academic_period` | Look up period from SIS |
| `ce/ethos/academic_periods/create_from_sis/` | `ethos:academic_year_create_from_sis` | Create academic year from SIS |
| `ce/ethos/sections/import/` | `ethos:ethos_section_import` | Trigger section import |
| `ce/ethos/sections/import/status/` | `ethos:ethos_section_import_status` | Poll import status |

### 5. Term Actions (component registry)

The `trigger_section_import` view in `ethos/views/sections.py` is registered as a term action via `@term_actions.action(...)`. The host app's `cis/views/term.py` must import `ethos.ethos.views.sections` (or `ethos.views.sections`) at module load time to trigger the decorator registration:

```python
import importlib.util as _util
if _util.find_spec('ethos.ethos'):
    import ethos.ethos.views.sections  # noqa: F401
else:
    import ethos.views.sections  # noqa: F401
```

Academic year and cohort actions are registered via string path handlers in `myce/component_registry/academic_year.py` and `myce/component_registry/cohort.py`.

### 6. CE Sidebar Menu

Add the following entry to the `ce_menu` JSON in the `cis.settings.menu` DB setting (via `/ce/settings/`). Insert it before the `users` entry:

```json
{
  "type": "nav-item",
  "icon": "fas fa-fw fa-plug",
  "label": "SIS",
  "name": "ethos",
  "sub_menu": [
    {
      "label": "All Resources",
      "name": "ethos_resources",
      "url": "ethos:ethos_resources"
    },
    {
      "label": "All Logs",
      "name": "ethos_logs",
      "url": "ethos:ethos_logs"
    },
    {
      "label": "Status",
      "name": "ethos_status",
      "url": "ethos:ethos_status"
    }
  ]
}
```

---

## Configuration

| Setting | Description |
|---|---|
| `COLLEAGUE_AUTH_CODE` | Ethos API auth code from Secrets Manager |

---

## Library Mixins

The `Ethos` class composes 15 mixins:

| Mixin | File | Key Methods |
|-------|------|-------------|
| `SectionDetailMixin` | `section_detail.py` | `get_section_meeting_times`, `get_section_instructors`, `get_section_enrollment_info`, `get_section_registrations`, `get_section_registration_statuses`, `get_section_grade_types` |
| `StudentRecordsMixin` | `student_records.py` | `get_student`, `get_student_academic_periods`, `get_student_academic_programs`, `get_student_course_registrations`, `get_student_academic_standings`, `get_enrollment_statuses`, `get_student_types` |
| `StudentAccountMixin` | `student_account.py` | `get_account_summary`, `get_account_details`, `get_account_memos`, `get_financial_aid_awards`, `get_financial_aid_years` |
| `GradesMixin` | `grades.py` | `get_student_grades`, `get_grade_definitions`, `get_grade_modes`, `get_student_gpa`, `get_section_grade_types`, `submit_student_grade` |
| `HoldsMixin` | `holds.py` | `get_person_holds`, `get_person_hold`, `get_hold_type_codes`, `get_person_hold_types`, `release_person_hold` |
| `ReferenceMixin` | `reference.py` | `get_academic_levels`, `get_instructional_methods`, `get_grade_schemes`, `get_academic_catalogs`, `get_educational_institution`, `get_educational_institutions` |
| `PersonMixin` | `person.py` | `get_or_create_person`, `update_person`, `get_person`, `get_bannerid`, `create_external_ed`, `send_emergency_contact`, `put_misc_info` |
| `AcademicMixin` | `academic.py` | `create_admission_application`, `accept_admission_decision`, `submit_academic_program`, `get_academic_programs`, `get_sites` |
| `AcademicPeriodsMixin` | `academic_periods.py` | `get_academic_periods`, `get_academic_period_id`, `get_child_academic_periods` |
| `RegistrationMixin` | `registration.py` | `sendRegistrationHold`, `mirror_registration`, `mirror_linked_registrations`, `update_registration`, `update_registration_status` |
| `PaymentMixin` | `payment.py` | `assess_fee`, `sendStudentFRL`, `sendStudentPayment` |
| `SectionMixin` | `section.py` | `get_sections` (paginated) |
| `CoursesMixin` | `courses.py` | `get_courses` (paginated), `get_course_by_id` |
| `SubjectsMixin` | `subjects.py` | `get_subjects`, `get_subject_by_id` |
| `AdminMixin` | `admin.py` | `get_available_resources` |

### Accept Header Preference

Every method that sends an Accept header uses:
```python
accept = self.get_preferred_accept_header('resource-name') or 'application/vnd.hedtech.integration.vN+json'
```

The preferred header is set per-resource from `/ce/ethos/resources/<pk>/` — select a representation row and click **Set**. The preference is stored in `EthosResource.preferred_representation` and applied automatically at call time.

---

## Management Commands

```bash
python manage.py import_subjects_from_ethos
python manage.py import_terms_from_ethos <year_code>
python manage.py import_courses_from_ethos <term_code>
python manage.py import_sections_from_ethos <term_code> --create
python manage.py sync_ethos_resources
```

## Background Task Worker

```bash
docker exec django_web_ewu python /app/webapp/manage.py db_worker
```

## UI Integration

- The term detail page (`/ce/term/<id>`) has a "Pull Sections from SIS" action that enqueues `import_sections_for_term` and polls for completion.
- The academic year add page (`/ce/academic_year/add_new`) has a "Import from SIS" flow for looking up and creating periods from Ethos.
- The resource browser at `/ce/ethos/resources` shows all available Ethos API resources with their supported methods and representations. Click a row to open the modal detail and set a preferred Accept header.
- The API log viewer at `/ce/ethos/logs` shows every Ethos API call with request/response details accessible via modal.
- The API Explorer at `/ce/ethos/status` allows admins to call any of the 44 registered Ethos methods interactively with optional `offset`/`limit` slicing.

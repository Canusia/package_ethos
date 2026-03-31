# Ethos Integration — Technical API Reference

Ellucian Ethos SIS integration client for MyCE. Provides Django views, a Python client library, and background tasks for syncing Student Information System data (academic periods, sections, courses, subjects, persons) through the Ethos Integration platform.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Base URL & Infrastructure](#base-url--infrastructure)
3. [Django Endpoints](#django-endpoints)
   - [API Explorer](#api-explorer)
   - [Academic Periods](#academic-periods)
   - [Sections Import](#sections-import)
   - [Subjects](#subjects)
4. [Python Client Methods](#python-client-methods)
   - [Academic Periods](#academic-periods-client)
   - [Subjects](#subjects-client)
   - [Courses](#courses-client)
   - [Sections](#sections-client)
   - [Persons](#persons-client)
   - [Sites & Programs](#sites--programs-client)
5. [Data Structures](#data-structures)
6. [Pagination](#pagination)
7. [Background Tasks](#background-tasks)
8. [Error Handling](#error-handling)

---

## Authentication

### Django Endpoints

All Django views require the `ce` (CE administrator) role. Requests that fail this check receive a redirect to the login page.

### Ethos API (upstream)

JWT Bearer Token obtained from the Ellucian Ethos Integration service.

- **Token endpoint:** `POST https://integrate.elluciancloud.com/auth`
- **Configuration:** `COLLEAGUE_AUTH_CODE` Django setting (API key sourced from AWS Secrets Manager in production)
- **Caching:** Token is cached in memory with a 30-second expiry buffer to avoid unnecessary re-auth

```http
POST https://integrate.elluciancloud.com/auth
Authorization: Bearer <COLLEAGUE_AUTH_CODE>
```

**Response:** JWT token string used as the `Authorization` header for all subsequent Ethos API calls.

---

## Base URL & Infrastructure

**Ethos API base:** `https://integrate.elluciancloud.com`

All requests go through `EthosBase._api_request()` which:
- Injects the cached JWT token
- Logs every call to `cis.models.sis.SIS_Log` for audit purposes
- Handles retries and token refresh on 401

---

## Django Endpoints

All endpoints are mounted under `/ce/ethos/` and require CE role authentication.

---

### API Explorer

#### `GET /ce/ethos/status/`

Renders an interactive API Explorer UI listing all available client methods with a form to invoke them.

**Response:** HTML page

---

#### `POST /ce/ethos/status/run/`

Executes an Ethos client method and returns the raw result. Intended for the API Explorer UI and debugging.

**Request headers:**
```
Content-Type: application/json
```

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `method_name` | string | yes | Name of the client method to invoke (see allowlist below) |
| `params` | object | no | Key-value parameters forwarded to the method |

**Allowed method names:**
- `get_academic_periods`
- `get_academic_period_id`
- `get_child_academic_periods`
- `get_subjects`
- `get_subject_by_id`
- `get_courses`
- `get_course_by_id`
- `get_sections`
- `get_sites`
- `get_academic_programs`
- `get_person`

**Example — fetch term-level academic periods:**

```http
POST /ce/ethos/status/run/
Content-Type: application/json

{
  "method_name": "get_academic_periods",
  "params": {
    "category": "term",
    "limit": 5
  }
}
```

```json
{
  "result": [
    {
      "id": "0840696f-a9c4-46d9-acbc-1e335c240155",
      "code": "202620",
      "title": "Spring 2026",
      "category": {
        "type": "term",
        "parent": { "id": "year-guid" }
      },
      "startOn": "2026-01-15",
      "endOn": "2026-05-31"
    },
    {
      "id": "1a2b3c4d-0000-0000-0000-000000000001",
      "code": "202630",
      "title": "Summer 2026",
      "category": {
        "type": "term",
        "parent": { "id": "year-guid" }
      },
      "startOn": "2026-06-15",
      "endOn": "2026-08-15"
    }
  ]
}
```

**Example — fetch a person by Ethos GUID:**

```http
POST /ce/ethos/status/run/
Content-Type: application/json

{
  "method_name": "get_person",
  "params": {
    "personid": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
  }
}
```

```json
{
  "result": {
    "bannerid": "A00123456",
    "other_email": "john.doe@ewu.edu"
  }
}
```

**Error responses:**

```json
{ "error": "Method not allowed" }
```
```json
{ "error": "Missing required parameter: method_name" }
```

---

### Academic Periods

#### `GET /ce/ethos/academic_periods/lookup/`

Looks up an academic year and its descendant terms/subterms from Ethos.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `code` | string | yes | Academic period code, e.g. `"2026"` or `"202620"` |

**Example request:**

```http
GET /ce/ethos/academic_periods/lookup/?code=2026
```

**Success response:**

```json
{
  "status": "success",
  "year": {
    "id": "year-uuid-0001",
    "code": "2026",
    "title": "2026 Academic Year",
    "startOn": "2025-08-01",
    "endOn": "2026-05-31",
    "category": { "type": "year" }
  },
  "children": [
    {
      "period": {
        "id": "fall-uuid-0001",
        "code": "202610",
        "title": "Fall 2025",
        "startOn": "2025-08-25",
        "endOn": "2025-12-15",
        "category": { "type": "term", "parent": { "id": "year-uuid-0001" } }
      },
      "children": []
    },
    {
      "period": {
        "id": "spring-uuid-0001",
        "code": "202620",
        "title": "Spring 2026",
        "startOn": "2026-01-15",
        "endOn": "2026-05-31",
        "category": { "type": "term", "parent": { "id": "year-uuid-0001" } }
      },
      "children": []
    }
  ]
}
```

**Warning response (no matching period found):**

```json
{
  "status": "warning",
  "message": "No academic period found with code \"9999\""
}
```

---

#### `POST /ce/ethos/academic_periods/create_from_sis/`

Creates `AcademicYear` and `Term` database records from Ethos data returned by the lookup endpoint.

**Request headers:**
```
Content-Type: application/json
```

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `year` | object | yes | Academic year data from Ethos |
| `year.id` | string | yes | Ethos GUID |
| `year.code` | string | yes | Year code, e.g. `"2026"` |
| `year.title` | string | yes | Display name |
| `terms` | array | yes | Term objects to create (subset selected by user) |
| `terms[].id` | string | yes | Ethos GUID |
| `terms[].code` | string | yes | Term code, e.g. `"202620"` |
| `terms[].title` | string | yes | Term display name |
| `terms[].startOn` | string | no | ISO 8601 start date |
| `terms[].endOn` | string | no | ISO 8601 end date |

**Example request:**

```http
POST /ce/ethos/academic_periods/create_from_sis/
Content-Type: application/json

{
  "year": {
    "id": "year-uuid-0001",
    "code": "2026",
    "title": "2026 Academic Year"
  },
  "terms": [
    {
      "id": "spring-uuid-0001",
      "code": "202620",
      "title": "Spring 2026",
      "startOn": "2026-01-15",
      "endOn": "2026-05-31"
    },
    {
      "id": "summer-uuid-0001",
      "code": "202630",
      "title": "Summer 2026",
      "startOn": "2026-06-15",
      "endOn": "2026-08-15"
    }
  ]
}
```

**Success response:**

```json
{
  "status": "success",
  "message": "Created academic year \"2026 Academic Year\" with 2 term(s).",
  "academic_year_id": "db-pk-001",
  "academic_year_name": "2026 Academic Year"
}
```

**Error response:**

```json
{
  "status": "error",
  "message": "Academic year with code \"2026\" already exists."
}
```

---

### Sections Import

#### `POST /ce/ethos/sections/import/`

Enqueues a background task to import sections from Ethos for one or more terms.

**Request body (form-encoded):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ids[]` | array of strings | no | Term database IDs |
| `record_id` | string | no | Single term ID (fallback if `ids[]` absent) |

**Example request:**

```http
POST /ce/ethos/sections/import/
Content-Type: application/x-www-form-urlencoded

ids[]=42&ids[]=43
```

**Response — task enqueued:**

```json
{
  "outcome": "poll",
  "poll_url": "/ce/ethos/sections/import/status/?task_id=bg-task-uuid-0001",
  "title": "Importing Sections",
  "message": "Section import is running…"
}
```

**Response — error:**

```json
{
  "outcome": "alert",
  "message": "No valid term IDs provided."
}
```

---

#### `GET /ce/ethos/sections/import/status/`

Polls the status of a running section import background task.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | yes | Background task ID from the import response |

**Example request:**

```http
GET /ce/ethos/sections/import/status/?task_id=bg-task-uuid-0001
```

**Response — task still running:**

```json
{ "status": "RUNNING" }
```

**Response — task pending (queued, not started):**

```json
{ "status": "PENDING" }
```

**Response — task succeeded:**

```json
{
  "status": "SUCCEEDED",
  "counts": {
    "total_fetched": 120,
    "created": 80,
    "updated": 30,
    "skipped": 10
  }
}
```

**Response — task failed:**

```json
{
  "status": "FAILED",
  "error": "ConnectionError"
}
```

---

### Subjects

#### `GET /ce/ethos/subjects/lookup/`

Fetches subjects from Ethos, optionally filtered by abbreviation.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `abbreviation` | string | no | Subject code to filter, e.g. `"MATH"` |

**Example request:**

```http
GET /ce/ethos/subjects/lookup/?abbreviation=MATH
```

**Success response:**

```json
{
  "status": "success",
  "subjects": [
    {
      "id": "subj-uuid-math",
      "code": "MATH",
      "abbreviation": "MATH",
      "title": "Mathematics",
      "description": "Department of Mathematics"
    }
  ]
}
```

**Warning response (no results):**

```json
{
  "status": "warning",
  "message": "No subjects found matching \"PHYS9\""
}
```

---

#### `POST /ce/ethos/subjects/create_from_sis/`

Creates `Cohort` (subject/department) records from Ethos subject data.

**Request headers:**
```
Content-Type: application/json
```

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `subjects` | array | yes | Subject objects to sync |
| `subjects[].id` | string | yes | Ethos GUID |
| `subjects[].abbreviation` | string | yes | Subject code |
| `subjects[].title` | string | yes | Display name |

**Example request:**

```http
POST /ce/ethos/subjects/create_from_sis/
Content-Type: application/json

{
  "subjects": [
    {
      "id": "subj-uuid-math",
      "abbreviation": "MATH",
      "title": "Mathematics"
    },
    {
      "id": "subj-uuid-cs",
      "abbreviation": "CS",
      "title": "Computer Science"
    }
  ]
}
```

**Success response:**

```json
{
  "status": "success",
  "message": "Synced 2 subject(s). Created: 2, Updated: 0."
}
```

---

## Python Client Methods

All methods are available on the `Ethos` class, which composes mixins:

```python
from ethos.ethos.library.ethos import Ethos

client = Ethos()
```

---

### Academic Periods Client

#### `get_academic_periods(code=None, category=None, **kwargs)`

Fetches academic periods from Ethos with optional filtering.

| Parameter | Type | Description |
|-----------|------|-------------|
| `code` | str | Filter by period code, e.g. `"2026"` or `"202620"` |
| `category` | str | Filter by type: `"year"`, `"term"`, or `"subterm"` |

```python
periods = client.get_academic_periods(category="term")
# Returns list of period dicts
```

**Sample return value:**

```python
[
    {
        "id": "0840696f-a9c4-46d9-acbc-1e335c240155",
        "code": "202620",
        "title": "Spring 2026",
        "category": {"type": "term", "parent": {"id": "year-guid"}},
        "startOn": "2026-01-15",
        "endOn": "2026-05-31"
    }
]
```

---

#### `get_academic_period_id(code)`

Returns the Ethos GUID for an academic period given its code, or `None` if not found.

```python
guid = client.get_academic_period_id("202620")
# "0840696f-a9c4-46d9-acbc-1e335c240155"
```

---

#### `get_child_academic_periods(parent, depth=2, **kwargs)`

Recursively fetches descendant periods.

| Parameter | Type | Description |
|-----------|------|-------------|
| `parent` | str | Parent period code or GUID |
| `depth` | int | Levels to traverse (default `2`, max `4`) |

```python
children = client.get_child_academic_periods("2026", depth=2)
```

---

### Subjects Client

#### `get_subjects(abbreviation=None, **kwargs)`

Fetches subjects with optional abbreviation filter.

```python
subjects = client.get_subjects(abbreviation="MATH")
```

**Sample return value:**

```python
[
    {
        "id": "subj-uuid-math",
        "code": "MATH",
        "abbreviation": "MATH",
        "title": "Mathematics",
        "description": "Department of Mathematics"
    }
]
```

---

#### `get_subject_by_id(subject_id, **kwargs)`

Fetches a single subject by Ethos GUID.

```python
subject = client.get_subject_by_id("subj-uuid-math")
```

---

### Courses Client

#### `get_courses(number=None, title=None, **kwargs)`

Fetches courses with optional filtering.

| Parameter | Type | Description |
|-----------|------|-------------|
| `number` | str | Course number, e.g. `"101"` |
| `title` | str | Partial course title, e.g. `"Calculus"` |

```python
courses = client.get_courses(number="101")
```

**Sample return value:**

```python
[
    {
        "id": "course-uuid-0001",
        "number": "101",
        "title": "Introduction to Calculus",
        "description": "First calculus course in the sequence",
        "creditHours": 4.0,
        "subject": {
            "id": "subj-uuid-math",
            "abbreviation": "MATH"
        }
    }
]
```

---

#### `get_course_by_id(course_id, **kwargs)`

Fetches a single course by Ethos GUID.

```python
course = client.get_course_by_id("course-uuid-0001")
```

---

### Sections Client

#### `get_sections(term_code=None, period_id=None, **kwargs)`

Fetches all sections for an academic period. Automatically paginates through all pages.

| Parameter | Type | Description |
|-----------|------|-------------|
| `term_code` | str | Term code, e.g. `"202620"` — resolved to GUID internally |
| `period_id` | str | Ethos academic period GUID (skips code lookup if provided) |

Uses the `sections-maximum` Ethos resource type for full section detail.

```python
sections = client.get_sections(term_code="202620")
# or
sections = client.get_sections(period_id="0840696f-a9c4-46d9-acbc-1e335c240155")
```

**Sample return value:**

```python
[
    {
        "id": "section-uuid-0001",
        "number": "001",
        "code": "MATH101-001",
        "course": {
            "id": "course-uuid-0001",
            "number": "101",
            "title": "Introduction to Calculus"
        },
        "academicPeriod": {
            "id": "0840696f-a9c4-46d9-acbc-1e335c240155"
        },
        "instructors": [
            {
                "instructor": {
                    "id": "person-uuid-0001"
                }
            }
        ],
        "credits": [
            {
                "measure": "credit",
                "minimum": 4.0,
                "maximum": 4.0
            }
        ],
        "meetingPatterns": [
            {
                "daysOfWeek": ["monday", "wednesday", "friday"],
                "startTime": "09:00:00",
                "endTime": "09:50:00",
                "room": { "id": "room-uuid-0001" }
            }
        ]
    }
]
```

---

### Persons Client

#### `get_person(personid, **kwargs)`

Retrieves a person record by Ethos GUID and returns extracted key fields.

```python
person = client.get_person("f47ac10b-58cc-4372-a567-0e02b2c3d479")
```

**Sample return value:**

```python
{
    "bannerid": "A00123456",
    "other_email": "john.doe@ewu.edu"
}
```

**Full raw Ethos person record structure (before extraction):**

```python
{
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "credentials": [
        {"type": {"credentialType": "bannerId"}, "value": "A00123456"},
        {"type": {"credentialType": "colleagueId"}, "value": "12345"}
    ],
    "names": [
        {
            "firstName": "John",
            "middleName": "Robert",
            "lastName": "Doe",
            "fullName": "John Robert Doe",
            "preference": "preferred",
            "type": {"category": "personal"}
        }
    ],
    "emails": [
        {
            "address": "john.doe@ewu.edu",
            "type": {"emailType": "personal"},
            "preference": "primary"
        }
    ],
    "addresses": [...],
    "phones": [...]
}
```

---

### Sites & Programs Client

#### `get_sites(**kwargs)`

Lists all available campus sites.

```python
sites = client.get_sites()
```

**Sample return value:**

```python
[
    {
        "id": "site-uuid-main",
        "code": "MAIN",
        "title": "Main Campus"
    },
    {
        "id": "site-uuid-online",
        "code": "ONLINE",
        "title": "Online"
    }
]
```

---

#### `get_academic_programs(code=None)`

Lists academic programs, optionally filtered by code.

```python
programs = client.get_academic_programs(code="CE")
```

---

## Data Structures

### Academic Period

```json
{
  "id": "uuid",
  "code": "202620",
  "title": "Spring 2026",
  "description": "Spring 2026 Term",
  "startOn": "2026-01-15",
  "endOn": "2026-05-31",
  "category": {
    "type": "term",
    "parent": { "id": "parent-year-uuid" }
  }
}
```

`category.type` values: `"year"`, `"term"`, `"subterm"`

---

### Course

```json
{
  "id": "uuid",
  "number": "101",
  "title": "Introduction to Calculus",
  "description": "First calculus course",
  "creditHours": 4.0,
  "subject": {
    "id": "subject-uuid",
    "abbreviation": "MATH"
  }
}
```

---

### Section

```json
{
  "id": "uuid",
  "number": "001",
  "code": "MATH101-001",
  "course": {
    "id": "course-uuid",
    "number": "101",
    "title": "Introduction to Calculus"
  },
  "academicPeriod": {
    "id": "period-uuid"
  },
  "instructors": [
    { "instructor": { "id": "person-uuid" } }
  ],
  "credits": [
    { "measure": "credit", "minimum": 4.0, "maximum": 4.0 }
  ],
  "meetingPatterns": [
    {
      "daysOfWeek": ["monday", "wednesday", "friday"],
      "startTime": "09:00:00",
      "endTime": "09:50:00",
      "room": { "id": "room-uuid" }
    }
  ]
}
```

---

### Subject

```json
{
  "id": "uuid",
  "code": "MATH",
  "abbreviation": "MATH",
  "title": "Mathematics",
  "description": "Department of Mathematics"
}
```

---

### Person (raw Ethos)

```json
{
  "id": "uuid",
  "credentials": [
    { "type": { "credentialType": "bannerId" }, "value": "A00123456" },
    { "type": { "credentialType": "colleagueId" }, "value": "12345" }
  ],
  "names": [
    {
      "firstName": "Jane",
      "middleName": "Marie",
      "lastName": "Smith",
      "fullName": "Jane Marie Smith",
      "preference": "preferred",
      "type": { "category": "personal" }
    }
  ],
  "emails": [
    {
      "address": "jane.smith@ewu.edu",
      "type": { "emailType": "personal" },
      "preference": "primary"
    }
  ]
}
```

---

## Pagination

Ethos API uses offset-based pagination. The Python client methods automatically fetch all pages.

**Ethos response headers:**

| Header | Description |
|--------|-------------|
| `x-total-count` | Total number of records in the full result set |
| `x-max-page-size` | Maximum records per page (typically `500`) |

**Manual pagination (via API Explorer):**

```json
{
  "method_name": "get_academic_periods",
  "params": {
    "offset": 0,
    "limit": 25
  }
}
```

---

## Background Tasks

Section imports run as `django-tasks` background tasks on the `default` queue.

### `import_sections_for_term(term_id: str) -> dict`

Defined in `ethos/tasks.py`.

**Process:**
1. Load the `Term` record by `term_id`
2. Resolve Ethos academic period GUID from the term's SIS code
3. Fetch all raw sections via `Ethos().get_sections(period_id=...)`
4. Run `SectionImporter().import_sections(raw_sections, term=term)`
5. Return counts dict

**Return value:**

```python
{
    "total_fetched": 120,
    "created": 80,
    "updated": 30,
    "skipped": 10,
    "error": None        # exception class name string if failed, else None
}
```

---

## Error Handling

### Django endpoint errors

All endpoints return JSON with a `status` field of `"error"` or `"warning"`:

```json
{ "status": "error", "message": "Human-readable description" }
```

```json
{ "status": "warning", "message": "Non-fatal issue, e.g. no results found" }
```

The API Explorer endpoint (`/ce/ethos/status/run/`) uses an `"error"` key at the top level:

```json
{ "error": "Method not allowed" }
```

### Ethos API errors

The `_api_request` method raises on non-2xx responses. Connection failures propagate as standard Python exceptions (`requests.exceptions.ConnectionError`, `requests.exceptions.Timeout`, etc.) and are captured by the background task runner, which marks the task as `FAILED` and records the exception class name.

---

## File Structure

```
ethos/
├── ethos/
│   ├── apps.py
│   ├── library/
│   │   ├── base.py               # EthosBase: auth, _api_request, logging
│   │   ├── ethos.py              # Ethos class (mixin composition)
│   │   ├── academic_periods.py   # get_academic_periods, get_child_academic_periods
│   │   ├── section.py            # get_sections
│   │   ├── courses.py            # get_courses, get_course_by_id
│   │   ├── subjects.py           # get_subjects, get_subject_by_id
│   │   ├── person.py             # get_person, get_or_create_person, update_person
│   │   ├── academic.py           # get_sites, get_academic_programs
│   │   ├── registration.py       # mirror_registration, sendRegistrationHold
│   │   └── payment.py            # assess_fee, sendStudentFRL, sendStudentPayment
│   ├── views/
│   │   ├── status.py             # GET /status/, POST /status/run/
│   │   ├── academic_periods.py   # GET /academic_periods/lookup/, POST /create_from_sis/
│   │   ├── sections.py           # POST /sections/import/, GET /sections/import/status/
│   │   └── subjects.py           # GET /subjects/lookup/, POST /subjects/create_from_sis/
│   ├── urls.py
│   ├── tasks.py                  # import_sections_for_term background task
│   ├── migrations/
│   └── templates/ethos/
│       └── status.html           # API Explorer UI
├── tests/
├── setup.py
└── requirements.txt
```

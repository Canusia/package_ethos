"""
Ethos SIS Integration

Composes all domain mixins into a single Ethos client class.
All existing imports (``from ethos.library.ethos import Ethos``) continue
to work unchanged.
"""

from .person import PersonMixin
from .academic import AcademicMixin
from .academic_periods import AcademicPeriodsMixin
from .registration import RegistrationMixin
from .payment import PaymentMixin
from .section import SectionMixin
from .subjects import SubjectsMixin
from .courses import CoursesMixin
from .admin import AdminMixin
from .section_detail import SectionDetailMixin
from .student_records import StudentRecordsMixin
from .student_account import StudentAccountMixin
from .grades import GradesMixin
from .holds import HoldsMixin
from .reference import ReferenceMixin


class Recruiter:
    ...


class Ethos(
    SectionDetailMixin,
    StudentRecordsMixin,
    StudentAccountMixin,
    GradesMixin,
    HoldsMixin,
    ReferenceMixin,
    PersonMixin,
    AcademicMixin,
    AcademicPeriodsMixin,
    RegistrationMixin,
    PaymentMixin,
    SectionMixin,
    SubjectsMixin,
    CoursesMixin,
    AdminMixin,
):
    """Ellucian Ethos SIS integration client.

    Inherits all domain-specific operations from mixins:

    New (2026):
    - SectionDetailMixin: meeting times, instructors, enrollment info, registrations, grade types
    - StudentRecordsMixin: student record, academic periods/programs, course registrations, standings
    - StudentAccountMixin: account summary/details/memos, financial aid awards and years
    - GradesMixin: grade reads, grade definitions/modes/schemes, final grade submission
    - HoldsMixin: list/get/release person holds, hold type reference data
    - ReferenceMixin: academic levels, instructional methods, grade schemes, catalogs, institutions

    Existing:
    - PersonMixin: person CRUD, matching, credentials
    - AcademicMixin: programs, admissions
    - AcademicPeriodsMixin: academic periods lookup, filtering, pagination
    - RegistrationMixin: section registrations, holds, mirroring
    - PaymentMixin: payments, fees, FRL exemptions
    - SectionMixin: section fetching, formatting, messages
    - SubjectsMixin: subjects lookup, filtering, pagination
    - CoursesMixin: courses lookup, filtering, pagination
    - AdminMixin: admin endpoints (available resources, application registry)

    Core infrastructure (auth, API helpers, GUID loading) lives in
    EthosBase, which all mixins inherit from.
    """
    pass

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


class Recruiter:
    ...


class Ethos(PersonMixin, AcademicMixin, AcademicPeriodsMixin, RegistrationMixin, PaymentMixin, SectionMixin, SubjectsMixin, CoursesMixin, AdminMixin):
    """Ellucian Ethos SIS integration client.

    Inherits all domain-specific operations from mixins:
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

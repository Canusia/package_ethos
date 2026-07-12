from ..accept import accept_for
from ..output import emit
from . import add_output_flags


def _person_arg(parser):
    parser.add_argument("--person-id", dest="person_id", required=True,
                        help="Person GUID.")
    add_output_flags(parser)


def register(subparsers):
    p = subparsers.add_parser("student-records", help="Query student records.")
    sub = p.add_subparsers(dest="action", required=True)

    g = sub.add_parser("get", help="Get a student by person GUID.")
    _person_arg(g)
    g.set_defaults(func=cmd_get)

    ap = sub.add_parser("academic-periods", help="Student academic periods.")
    _person_arg(ap)
    ap.set_defaults(func=cmd_academic_periods)

    pr = sub.add_parser("programs", help="Student academic programs.")
    _person_arg(pr)
    pr.set_defaults(func=cmd_programs)

    cr = sub.add_parser("course-registrations", help="Student course registrations.")
    cr.add_argument("--person-id", dest="person_id", required=True)
    cr.add_argument("--period-id", dest="period_id",
                    help="Optional academic period GUID filter.")
    add_output_flags(cr)
    cr.set_defaults(func=cmd_course_registrations)

    st = sub.add_parser("standings", help="Student academic standings.")
    _person_arg(st)
    st.set_defaults(func=cmd_standings)

    es = sub.add_parser("enrollment-statuses", help="All enrollment statuses.")
    add_output_flags(es)
    es.set_defaults(func=cmd_enrollment_statuses)

    ty = sub.add_parser("types", help="All student types.")
    add_output_flags(ty)
    ty.set_defaults(func=cmd_types)


def cmd_get(client, args):
    record = client.get_entity("api/students", args.person_id,
                               accept=accept_for("students"))
    if not record:
        print("Not found.")
        return 0
    emit([record], args)
    return 0


def cmd_academic_periods(client, args):
    records = client.get_collection(
        "api/student-academic-periods",
        criteria={"student": {"id": args.person_id}},
        accept=accept_for("student-academic-periods"),
    )
    emit(records, args)
    return 0


def cmd_programs(client, args):
    records = client.get_collection(
        "api/student-academic-programs",
        criteria={"student": {"id": args.person_id}},
        accept=accept_for("student-academic-programs"),
    )
    emit(records, args)
    return 0


def cmd_course_registrations(client, args):
    criteria = {"registrant": {"id": args.person_id}}
    if args.period_id:
        criteria["academicPeriod"] = {"id": args.period_id}
    records = client.get_collection(
        "api/student-course-registrations", criteria=criteria,
        accept=accept_for("student-course-registrations"),
    )
    emit(records, args)
    return 0


def cmd_standings(client, args):
    records = client.get_collection(
        "api/student-academic-standings",
        criteria={"student": {"id": args.person_id}},
        accept=accept_for("student-academic-standings"),
    )
    emit(records, args)
    return 0


def cmd_enrollment_statuses(client, args):
    records = client.get_collection("api/enrollment-statuses",
                                    accept=accept_for("enrollment-statuses"))
    emit(records, args)
    return 0


def cmd_types(client, args):
    records = client.get_collection("api/student-types",
                                    accept=accept_for("student-types"))
    emit(records, args)
    return 0

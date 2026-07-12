from ..accept import accept_for
from ..output import emit
from . import add_output_flags


def register(subparsers):
    p = subparsers.add_parser("grades", help="Query grades.")
    sub = p.add_subparsers(dest="action", required=True)

    sg = sub.add_parser("student-grades", help="Grades for a student.")
    sg.add_argument("--person-id", dest="person_id", required=True)
    sg.add_argument("--period-id", dest="period_id")
    add_output_flags(sg)
    sg.set_defaults(func=cmd_student_grades)

    de = sub.add_parser("definitions", help="Grade definitions.")
    de.add_argument("--scheme-id", dest="scheme_id",
                    help="Optional grade-scheme GUID filter.")
    add_output_flags(de)
    de.set_defaults(func=cmd_definitions)

    mo = sub.add_parser("modes", help="Grade modes.")
    add_output_flags(mo)
    mo.set_defaults(func=cmd_modes)

    gp = sub.add_parser("gpa", help="Student grade point averages.")
    gp.add_argument("--person-id", dest="person_id", required=True)
    add_output_flags(gp)
    gp.set_defaults(func=cmd_gpa)

    st = sub.add_parser("section-grade-types", help="Grade types for a section.")
    st.add_argument("--section-id", dest="section_id", required=True)
    add_output_flags(st)
    st.set_defaults(func=cmd_section_grade_types)


def cmd_student_grades(client, args):
    criteria = {"student": {"id": args.person_id}}
    if args.period_id:
        criteria["academicPeriod"] = {"id": args.period_id}
    records = client.get_collection("api/student-grades", criteria=criteria,
                                    accept=accept_for("student-grades"))
    emit(records, args)
    return 0


def cmd_definitions(client, args):
    criteria = {"scheme": {"id": args.scheme_id}} if args.scheme_id else None
    records = client.get_collection("api/grade-definitions", criteria=criteria,
                                    accept=accept_for("grade-definitions"))
    emit(records, args)
    return 0


def cmd_modes(client, args):
    records = client.get_collection("api/grade-modes",
                                    accept=accept_for("grade-modes"))
    emit(records, args)
    return 0


def cmd_gpa(client, args):
    records = client.get_collection(
        "api/student-grade-point-averages",
        criteria={"student": {"id": args.person_id}},
        accept=accept_for("student-grade-point-averages"),
    )
    emit(records, args)
    return 0


def cmd_section_grade_types(client, args):
    records = client.get_collection(
        "api/section-grade-types",
        criteria={"section": {"id": args.section_id}},
        accept=accept_for("section-grade-types"),
    )
    emit(records, args)
    return 0

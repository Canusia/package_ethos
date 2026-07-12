from ..accept import accept_for
from ..output import emit
from . import add_output_flags


def register(subparsers):
    p = subparsers.add_parser("registration", help="Query registration data (read-only).")
    sub = p.add_subparsers(dest="action", required=True)

    el = sub.add_parser("eligibility", help="Registration eligibility for a student/term.")
    el.add_argument("--student-id", dest="student_id", required=True)
    el.add_argument("--period-id", dest="period_id", required=True)
    add_output_flags(el)
    el.set_defaults(func=cmd_eligibility)


def cmd_eligibility(client, args):
    records = client.get_collection(
        "api/student-registration-eligibilities",
        criteria={"student": {"id": args.student_id},
                  "academicPeriod": {"id": args.period_id}},
        accept=accept_for("student-registration-eligibilities"),
    )
    if not records:
        print("No eligibility record found.")
        return 0
    emit(records[:1], args)
    return 0

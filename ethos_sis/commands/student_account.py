from ..accept import accept_for
from ..output import emit
from . import add_output_flags


def register(subparsers):
    p = subparsers.add_parser("student-account", help="Query student account data.")
    sub = p.add_subparsers(dest="action", required=True)

    su = sub.add_parser("summary", help="Account summary.")
    su.add_argument("--person-id", dest="person_id", required=True)
    add_output_flags(su)
    su.set_defaults(func=cmd_summary)

    de = sub.add_parser("details", help="Account details.")
    de.add_argument("--person-id", dest="person_id", required=True)
    de.add_argument("--period-id", dest="period_id")
    add_output_flags(de)
    de.set_defaults(func=cmd_details)

    me = sub.add_parser("memos", help="Account memos.")
    me.add_argument("--person-id", dest="person_id", required=True)
    add_output_flags(me)
    me.set_defaults(func=cmd_memos)

    fa = sub.add_parser("financial-aid-awards", help="Financial aid awards.")
    fa.add_argument("--person-id", dest="person_id", required=True)
    fa.add_argument("--aid-year-id", dest="aid_year_id")
    add_output_flags(fa)
    fa.set_defaults(func=cmd_financial_aid_awards)

    fy = sub.add_parser("financial-aid-years", help="All financial aid years.")
    add_output_flags(fy)
    fy.set_defaults(func=cmd_financial_aid_years)


def cmd_summary(client, args):
    records = client.get_collection(
        "api/student-account-summaries",
        criteria={"student": {"id": args.person_id}},
        accept=accept_for("student-account-summaries"),
    )
    emit(records[:1], args)
    return 0


def cmd_details(client, args):
    criteria = {"student": {"id": args.person_id}}
    if args.period_id:
        criteria["academicPeriod"] = {"id": args.period_id}
    records = client.get_collection("api/student-account-details", criteria=criteria,
                                    accept=accept_for("student-account-details"))
    emit(records, args)
    return 0


def cmd_memos(client, args):
    records = client.get_collection(
        "api/student-account-memos",
        criteria={"student": {"id": args.person_id}},
        accept=accept_for("student-account-memos"),
    )
    emit(records, args)
    return 0


def cmd_financial_aid_awards(client, args):
    criteria = {"student": {"id": args.person_id}}
    if args.aid_year_id:
        criteria["aidYear"] = {"id": args.aid_year_id}
    records = client.get_collection("api/student-financial-aid-awards",
                                    criteria=criteria,
                                    accept=accept_for("student-financial-aid-awards"))
    emit(records, args)
    return 0


def cmd_financial_aid_years(client, args):
    records = client.get_collection("api/financial-aid-years",
                                    accept=accept_for("financial-aid-years"))
    emit(records, args)
    return 0

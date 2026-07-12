from ..accept import accept_for
from ..output import emit
from . import add_output_flags


def register(subparsers):
    p = subparsers.add_parser("academic", help="Query academic programs and sites.")
    sub = p.add_subparsers(dest="action", required=True)

    pr = sub.add_parser("programs", help="Academic programs.")
    pr.add_argument("--code", help="Optional program code filter.")
    add_output_flags(pr)
    pr.set_defaults(func=cmd_programs)

    si = sub.add_parser("sites", help="All sites.")
    add_output_flags(si)
    si.set_defaults(func=cmd_sites)


def cmd_programs(client, args):
    criteria = {"code": args.code} if args.code else None
    records = client.get_collection("api/academic-programs", criteria=criteria,
                                    accept=accept_for("academic-programs"))
    emit(records, args)
    return 0


def cmd_sites(client, args):
    records = client.get_collection("api/sites", accept=accept_for("sites"))
    emit(records, args)
    return 0

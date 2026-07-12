from ..accept import accept_for
from ..output import emit
from . import add_output_flags


def register(subparsers):
    p = subparsers.add_parser("admin", help="Ethos admin resources.")
    sub = p.add_subparsers(dest="action", required=True)

    rs = sub.add_parser("resources", help="List available Ethos resources.")
    add_output_flags(rs)
    rs.set_defaults(func=cmd_resources)


def cmd_resources(client, args):
    records = client.get_collection("admin/available-resources",
                                    accept=accept_for("available-resources"))
    emit(records, args)
    return 0

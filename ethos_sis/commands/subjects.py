from ..accept import accept_for
from ..output import emit
from . import add_output_flags

RESOURCE = "subjects"
PATH = "api/subjects"
COLUMNS = ["id", "abbreviation", "title"]


def register(subparsers):
    p = subparsers.add_parser("subjects", help="Query subjects.")
    sub = p.add_subparsers(dest="action", required=True)

    lp = sub.add_parser("list", help="List subjects.")
    lp.add_argument("--abbreviation", help="Filter by subject abbreviation.")
    add_output_flags(lp)
    lp.set_defaults(func=cmd_list)

    gp = sub.add_parser("get", help="Get one subject by id.")
    gp.add_argument("--id", required=True, help="Subject GUID.")
    add_output_flags(gp)
    gp.set_defaults(func=cmd_get)


def cmd_list(client, args):
    criteria = {}
    if args.abbreviation:
        criteria["abbreviation"] = args.abbreviation
    records = client.get_collection(
        PATH, criteria=criteria or None, accept=accept_for(RESOURCE)
    )
    emit(records, args, columns=COLUMNS)
    return 0


def cmd_get(client, args):
    record = client.get_entity(PATH, args.id, accept=accept_for(RESOURCE))
    if not record:
        print("Not found.")
        return 0
    emit([record], args, columns=COLUMNS)
    return 0

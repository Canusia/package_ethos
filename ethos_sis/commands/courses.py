from ..accept import accept_for
from ..output import emit
from . import add_output_flags

RESOURCE = "courses"
PATH = "api/courses"
COLUMNS = ["id", "number", "title"]


def register(subparsers):
    p = subparsers.add_parser("courses", help="Query courses.")
    sub = p.add_subparsers(dest="action", required=True)

    lp = sub.add_parser("list", help="List courses.")
    lp.add_argument("--number", help="Filter by course number.")
    lp.add_argument("--title", help="Filter by course title.")
    add_output_flags(lp)
    lp.set_defaults(func=cmd_list)

    gp = sub.add_parser("get", help="Get one course by id.")
    gp.add_argument("--id", required=True, help="Course GUID.")
    add_output_flags(gp)
    gp.set_defaults(func=cmd_get)


def cmd_list(client, args):
    criteria = {}
    if args.number:
        criteria["number"] = args.number
    if args.title:
        criteria["title"] = args.title
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

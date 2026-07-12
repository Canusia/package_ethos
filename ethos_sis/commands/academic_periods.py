import re

from ..accept import accept_for
from ..output import dotted_get, emit
from . import add_output_flags

RESOURCE = "academic-periods"
PATH = "api/academic-periods"
COLUMNS = ["id", "code", "title", "category.type"]

_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _is_guid(value) -> bool:
    return bool(value) and bool(_GUID_RE.match(str(value)))


def _resolve_period(client, value):
    if _is_guid(value):
        return client.get_entity(PATH, value, accept=accept_for(RESOURCE))
    rows = client.get_collection(
        PATH, criteria={"code": value}, accept=accept_for(RESOURCE)
    )
    return rows[0] if rows else None


def register(subparsers):
    p = subparsers.add_parser("academic-periods", help="Query academic periods.")
    sub = p.add_subparsers(dest="action", required=True)

    lp = sub.add_parser("list", help="List academic periods.")
    lp.add_argument("--code", help="Filter by period code, e.g. 24/FA.")
    lp.add_argument("--category", help="Filter by category type: year/term/subterm.")
    add_output_flags(lp)
    lp.set_defaults(func=cmd_list)

    gp = sub.add_parser("get", help="Get one period by GUID or code.")
    gp.add_argument("--id", required=True, help="Period GUID or code.")
    add_output_flags(gp)
    gp.set_defaults(func=cmd_get)

    cp = sub.add_parser("children", help="List direct child periods of a parent.")
    cp.add_argument("--parent", required=True, help="Parent period GUID or code.")
    add_output_flags(cp)
    cp.set_defaults(func=cmd_children)


def cmd_list(client, args):
    criteria = {}
    if args.code:
        criteria["code"] = args.code
    if args.category:
        criteria["category"] = {"type": args.category}
    records = client.get_collection(
        PATH, criteria=criteria or None, accept=accept_for(RESOURCE)
    )
    emit(records, args, columns=COLUMNS)
    return 0


def cmd_get(client, args):
    record = _resolve_period(client, args.id)
    if not record:
        print("Not found.")
        return 0
    emit([record], args, columns=COLUMNS)
    return 0


def cmd_children(client, args):
    parent = _resolve_period(client, args.parent)
    if not parent:
        print("Parent period not found.")
        return 0
    parent_id = parent.get("id")
    everything = client.get_collection(PATH, accept=accept_for(RESOURCE))
    children = [
        r for r in everything
        if dotted_get(r, "category.parent.id") == parent_id
    ]
    emit(children, args, columns=COLUMNS)
    return 0

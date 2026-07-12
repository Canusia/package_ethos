from ..accept import accept_for
from ..output import emit
from . import add_output_flags

RESOURCE = "persons"
PATH = "api/persons"


def register(subparsers):
    p = subparsers.add_parser("person", help="Query persons (read-only).")
    sub = p.add_subparsers(dest="action", required=True)

    gp = sub.add_parser("get", help="Get one person by GUID.")
    gp.add_argument("--id", required=True, help="Person GUID.")
    add_output_flags(gp)
    gp.set_defaults(func=cmd_get)

    lp = sub.add_parser("lookup", help="Find a person by a credential.")
    lp.add_argument("--banner-id", dest="banner_id", help="Banner ID credential.")
    lp.add_argument("--colleague-id", dest="colleague_id",
                    help="Colleague person id credential.")
    lp.add_argument("--alt-cred", dest="alt_cred",
                    help="Alternative credential value.")
    lp.add_argument("--alt-type-id", dest="alt_type_id",
                    help="Alternative credential type GUID (with --alt-cred).")
    add_output_flags(lp)
    lp.set_defaults(func=cmd_lookup)


def cmd_get(client, args):
    record = client.get_entity(PATH, args.id, accept=accept_for(RESOURCE))
    if not record:
        print("Not found.")
        return 0
    emit([record], args)
    return 0


def cmd_lookup(client, args):
    if args.banner_id:
        criteria = {"credentials": [{"type": "bannerId", "value": args.banner_id}]}
    elif args.colleague_id:
        criteria = {"credentials": [
            {"type": "colleaguePersonId", "value": args.colleague_id}]}
    elif args.alt_cred and args.alt_type_id:
        criteria = {"alternativeCredentials": [
            {"type": {"id": args.alt_type_id}, "value": args.alt_cred}]}
    else:
        raise ValueError(
            "Provide --banner-id, --colleague-id, or --alt-cred with --alt-type-id."
        )
    records = client.get_collection(PATH, criteria=criteria, accept=accept_for(RESOURCE))
    emit(records, args)
    return 0

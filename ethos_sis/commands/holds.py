from ..accept import accept_for
from ..output import emit
from . import add_output_flags


def register(subparsers):
    p = subparsers.add_parser("holds", help="Query person holds.")
    sub = p.add_subparsers(dest="action", required=True)

    lp = sub.add_parser("list", help="List holds for a person.")
    lp.add_argument("--person-id", dest="person_id", required=True)
    add_output_flags(lp)
    lp.set_defaults(func=cmd_list)

    gp = sub.add_parser("get", help="Get one hold by GUID.")
    gp.add_argument("--id", required=True)
    add_output_flags(gp)
    gp.set_defaults(func=cmd_get)

    tc = sub.add_parser("type-codes", help="All hold type codes.")
    add_output_flags(tc)
    tc.set_defaults(func=cmd_type_codes)

    ht = sub.add_parser("hold-types", help="All person hold types.")
    add_output_flags(ht)
    ht.set_defaults(func=cmd_hold_types)


def cmd_list(client, args):
    records = client.get_collection(
        "api/person-holds", criteria={"person": {"id": args.person_id}},
        accept=accept_for("person-holds"),
    )
    emit(records, args)
    return 0


def cmd_get(client, args):
    record = client.get_entity("api/person-holds", args.id,
                               accept=accept_for("person-holds"))
    if not record:
        print("Not found.")
        return 0
    emit([record], args)
    return 0


def cmd_type_codes(client, args):
    records = client.get_collection("api/hold-type-codes",
                                    accept=accept_for("hold-type-codes"))
    emit(records, args)
    return 0


def cmd_hold_types(client, args):
    records = client.get_collection("api/person-hold-types",
                                    accept=accept_for("person-hold-types"))
    emit(records, args)
    return 0

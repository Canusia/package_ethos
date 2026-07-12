from ..accept import accept_for
from ..output import emit
from . import add_output_flags
from .academic_periods import _resolve_period

RESOURCE = "sections"
PATH = "api/sections"
COLUMNS = ["id", "number", "academicPeriod.id"]


def register(subparsers):
    p = subparsers.add_parser("sections", help="Query course sections.")
    sub = p.add_subparsers(dest="action", required=True)

    lp = sub.add_parser("list", help="List sections for a term/period.")
    lp.add_argument("--term-code", dest="term_code",
                    help="Academic period code, e.g. 24/FA.")
    lp.add_argument("--period-id", dest="period_id",
                    help="Academic period GUID (skips code resolution).")
    lp.add_argument("--accept", help="Override the Accept media type.")
    add_output_flags(lp)
    lp.set_defaults(func=cmd_list)

    gp = sub.add_parser("get", help="Get one section by id.")
    gp.add_argument("--id", required=True, help="Section GUID.")
    gp.add_argument("--accept", help="Override the Accept media type.")
    add_output_flags(gp)
    gp.set_defaults(func=cmd_get)


def _period_id(client, args):
    if args.period_id:
        return args.period_id
    if args.term_code:
        period = _resolve_period(client, args.term_code)
        if not period:
            raise ValueError(f"No academic period found for code {args.term_code!r}.")
        return period.get("id")
    raise ValueError("Provide --term-code or --period-id.")


def cmd_list(client, args):
    accept = accept_for(RESOURCE, override=args.accept)
    period_id = _period_id(client, args)
    if "maximum" in accept:
        criteria = {"academicPeriod": {"detail": {"id": period_id}}}
    else:
        criteria = {"academicPeriod": {"id": period_id}}
    records = client.get_collection(PATH, criteria=criteria, accept=accept)
    emit(records, args, columns=COLUMNS)
    return 0


def cmd_get(client, args):
    accept = accept_for(RESOURCE, override=args.accept)
    record = client.get_entity(PATH, args.id, accept=accept)
    if not record:
        print("Not found.")
        return 0
    emit([record], args, columns=COLUMNS)
    return 0

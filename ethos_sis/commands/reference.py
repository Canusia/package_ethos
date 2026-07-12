import json

from ..accept import accept_for
from ..output import emit
from . import add_output_flags


def register(subparsers):
    p = subparsers.add_parser("reference", help="Query reference/code tables.")
    sub = p.add_subparsers(dest="action", required=True)

    for name, func, help_text in [
        ("academic-levels", cmd_academic_levels, "All academic levels."),
        ("instructional-methods", cmd_instructional_methods, "All instructional methods."),
        ("grade-schemes", cmd_grade_schemes, "All grade schemes."),
    ]:
        sp = sub.add_parser(name, help=help_text)
        add_output_flags(sp)
        sp.set_defaults(func=func)

    ac = sub.add_parser("academic-catalogs", help="Academic catalogs.")
    ac.add_argument("--year-id", dest="year_id",
                    help="Optional academic-year GUID filter.")
    add_output_flags(ac)
    ac.set_defaults(func=cmd_academic_catalogs)

    ins = sub.add_parser("institution", help="Get one educational institution by GUID.")
    ins.add_argument("--id", required=True)
    add_output_flags(ins)
    ins.set_defaults(func=cmd_institution)

    insl = sub.add_parser("institutions", help="List educational institutions.")
    insl.add_argument("--criteria", help="Raw JSON criteria object.")
    add_output_flags(insl)
    insl.set_defaults(func=cmd_institutions)


def _list(client, args, path, resource):
    records = client.get_collection(path, accept=accept_for(resource))
    emit(records, args)
    return 0


def cmd_academic_levels(client, args):
    return _list(client, args, "api/academic-levels", "academic-levels")


def cmd_instructional_methods(client, args):
    return _list(client, args, "api/instructional-methods", "instructional-methods")


def cmd_grade_schemes(client, args):
    return _list(client, args, "api/grade-schemes", "grade-schemes")


def cmd_academic_catalogs(client, args):
    criteria = {"academicYear": {"id": args.year_id}} if args.year_id else None
    records = client.get_collection("api/academic-catalogs", criteria=criteria,
                                    accept=accept_for("academic-catalogs"))
    emit(records, args)
    return 0


def cmd_institution(client, args):
    record = client.get_entity("api/educational-institutions", args.id,
                               accept=accept_for("educational-institutions"))
    if not record:
        print("Not found.")
        return 0
    emit([record], args)
    return 0


def cmd_institutions(client, args):
    criteria = None
    if args.criteria:
        try:
            criteria = json.loads(args.criteria)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--criteria is not valid JSON: {exc}") from exc
    records = client.get_collection("api/educational-institutions", criteria=criteria,
                                    accept=accept_for("educational-institutions"))
    emit(records, args)
    return 0

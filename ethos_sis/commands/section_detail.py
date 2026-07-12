from ..accept import accept_for
from ..output import emit
from . import add_output_flags


def _section_arg(parser):
    parser.add_argument("--section-id", dest="section_id", required=True,
                        help="Section GUID.")
    add_output_flags(parser)


def register(subparsers):
    p = subparsers.add_parser("section-detail", help="Query section sub-resources.")
    sub = p.add_subparsers(dest="action", required=True)

    mt = sub.add_parser("meeting-times", help="Section meeting times.")
    _section_arg(mt)
    mt.set_defaults(func=cmd_meeting_times)

    ins = sub.add_parser("instructors", help="Section instructors.")
    _section_arg(ins)
    ins.set_defaults(func=cmd_instructors)

    en = sub.add_parser("enrollment", help="Section enrollment information.")
    _section_arg(en)
    en.set_defaults(func=cmd_enrollment)

    reg = sub.add_parser("registrations", help="Section registrations (roster).")
    _section_arg(reg)
    reg.set_defaults(func=cmd_registrations)

    gt = sub.add_parser("grade-types", help="Section grade types.")
    _section_arg(gt)
    gt.set_defaults(func=cmd_grade_types)

    rs = sub.add_parser("registration-statuses", help="All section registration statuses.")
    add_output_flags(rs)
    rs.set_defaults(func=cmd_registration_statuses)


def _by_section(client, args, path, resource):
    records = client.get_collection(
        path, criteria={"section": {"id": args.section_id}},
        accept=accept_for(resource),
    )
    emit(records, args)
    return 0


def cmd_meeting_times(client, args):
    return _by_section(client, args, "api/section-meeting-times", "section-meeting-times")


def cmd_instructors(client, args):
    return _by_section(client, args, "api/section-instructors", "section-instructors")


def cmd_registrations(client, args):
    return _by_section(client, args, "api/section-registrations", "section-registrations")


def cmd_grade_types(client, args):
    return _by_section(client, args, "api/section-grade-types", "section-grade-types")


def cmd_enrollment(client, args):
    record = client.get_entity(
        "api/section-enrollment-information", args.section_id,
        accept=accept_for("section-enrollment-information"),
    )
    if not record:
        print("Not found.")
        return 0
    emit([record], args)
    return 0


def cmd_registration_statuses(client, args):
    records = client.get_collection(
        "api/section-registration-statuses",
        accept=accept_for("section-registration-statuses"),
    )
    emit(records, args)
    return 0

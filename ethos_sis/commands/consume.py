"""Change-notification queue (/consume) — Ethos' message broker."""

from ..output import emit
from . import add_output_flags


COLUMNS = [
    "id",
    "published",
    "operation",
    "resource.name",
    "resource.id",
    "resource.version",
    "publisher.id",
]


def register(subparsers):
    p = subparsers.add_parser(
        "consume",
        help="Read change-notifications from this application's queue.",
        description=(
            "Read change-notifications published to this Ethos application's "
            "subscription queue. Reading DRAINS the queue: messages returned "
            "here will not be returned again unless you replay them with "
            "--last-processed-id. Use --peek to check the depth without "
            "consuming anything."
        ),
    )
    p.add_argument("--limit", type=int, default=None,
                   help="Max messages to retrieve, 1-1000 (payload also caps at 1 MB).")
    p.add_argument("--last-processed-id", dest="last_processed_id", type=int,
                   default=None,
                   help="Replay: return messages published after this notification ID.")
    p.add_argument("--peek", action="store_true",
                   help="Report queue depth only (HEAD /consume); does not drain.")
    add_output_flags(p)
    p.set_defaults(func=cmd_consume)


def cmd_consume(client, args):
    if args.peek:
        print(f"{client.available_message_count()} message(s) in the queue.")
        return 0

    records, remaining = client.consume_messages(
        limit=args.limit, last_processed_id=args.last_processed_id
    )
    emit(records, args, COLUMNS)
    if remaining is not None and not getattr(args, "json", False):
        print(f"{remaining} message(s) remaining in the queue.")
    return 0

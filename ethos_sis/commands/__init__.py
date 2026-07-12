"""Domain command modules. Each exposes register(subparsers).

Phase-2 tasks append their module to COMMAND_MODULES below.
"""


def add_output_flags(parser) -> None:
    parser.add_argument("--json", action="store_true",
                        help="Print raw JSON instead of a table.")
    parser.add_argument("--out", metavar="FILE",
                        help="Write results to a CSV file.")


# Populated by Phase-2 tasks (import each module and append it here).
COMMAND_MODULES: list = []

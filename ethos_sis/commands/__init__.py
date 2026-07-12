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

from . import subjects  # noqa: E402
COMMAND_MODULES.append(subjects)

from . import courses  # noqa: E402
COMMAND_MODULES.append(courses)

from . import academic_periods  # noqa: E402
COMMAND_MODULES.append(academic_periods)

from . import sections  # noqa: E402
COMMAND_MODULES.append(sections)

from . import section_detail  # noqa: E402
COMMAND_MODULES.append(section_detail)

from . import person  # noqa: E402
COMMAND_MODULES.append(person)

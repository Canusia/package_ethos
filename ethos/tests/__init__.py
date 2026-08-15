"""Test package for ethos.

`PKG` is the app's importable dotted path, resolved at runtime. The package
ships in two layouts — nested as an editable git submodule (`ethos.ethos`) and
flat when pip-installed (`ethos`) — and `mock.patch` targets and the dotted
handler paths in `ETHOS_CONSUME_HANDLERS` are strings, so they cannot rely on
Python's relative-import machinery the way `from ..models import x` can.

Hardcoding either layout means the shipped suite cannot run on tenants using
the other. That failure has been filed twice against sibling packages —
ewu#61 (highschool_admin) and ewu#62 (class_visit) — so it is a known trap,
not a hypothetical one.

Import statements in these tests use the `find_spec` conditional (needed
because the two layouts are genuinely different absolute paths); only
dotted-path *strings* need `PKG`.
"""
import importlib.util

PKG = 'ethos.ethos' if importlib.util.find_spec('ethos.ethos') else 'ethos'

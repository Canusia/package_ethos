from __future__ import annotations

import csv
import json


def dotted_get(record, path: str):
    value = record
    for segment in path.split("."):
        if isinstance(value, dict) and segment in value:
            value = value[segment]
        else:
            return ""
    return value


def _cell(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return "" if value is None else str(value)


def print_table(records: list, columns: list[str]) -> None:
    rows = [[_cell(dotted_get(r, c)) for c in columns] for r in records]
    widths = [len(c) for c in columns]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    header = "  ".join(c.ljust(widths[i]) for i, c in enumerate(columns))
    print(header)
    print("  ".join("-" * widths[i] for i in range(len(columns))))
    for row in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    print(f"\n{len(records)} row(s).")


def write_csv(records: list, path: str, columns: list[str] | None) -> None:
    if columns is None:
        seen: list[str] = []
        for r in records:
            for k in r:
                if k not in seen:
                    seen.append(k)
        columns = seen
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for r in records:
            writer.writerow([_cell(dotted_get(r, c)) for c in columns])


def emit(records: list, args, columns: list[str] | None = None) -> None:
    if getattr(args, "json", False):
        print(json.dumps(records, indent=2, default=str))
        return
    if getattr(args, "out", None):
        write_csv(records, args.out, columns)
        print(f"Wrote {len(records)} row(s) to {args.out}")
        return
    if not records:
        print("No results.")
        return
    if columns:
        print_table(records, columns)
    else:
        print(json.dumps(records, indent=2, default=str))

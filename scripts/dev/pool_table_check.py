#!/usr/bin/env python3
"""Check a pool prediction table against its Challenge's native checks and say, per output column, what is wrong.

The proof grid grades a model through a table of its raw outputs at every pool input row
(``pool_predict_table.py``). A table whose values are not in the Challenge's native space fails the version's
physics gates on every row (F08: ``finite_native_summary`` = non-finite, negative, wrong width, or a peak
frequency outside the registered band). This reads a table and prints, without any truth or limit: the rows and
width against the interface, each output column's finite count, negatives, min and max, and how many rows fail
each of the version's physics gates (the ones the grid applies to every answer). Nothing is written.

    python -B scripts/dev/pool_table_check.py --table table-f08-good.json --kind f08 --version 1.6
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path


def check(table, kind, version) -> dict:
    """``{"rows", "width", "expected_width", "columns": [...], "gate_failures": {...}}`` for a loaded table."""
    from carbon.scoring import pool_adapters

    gates = pool_adapters.physics_gates(kind, version)
    names = output_names(kind, version)
    rows = table["rows"]
    widths = sorted({len(r["raw"]) for r in rows})
    columns = []
    for j in range(max(widths) if widths else 0):
        values = [r["raw"][j] for r in rows if len(r["raw"]) > j]
        finite = [v for v in values if type(v) in (int, float) and math.isfinite(v)]
        columns.append(
            {
                "name": names[j] if j < len(names) else f"#{j}",
                "values": len(values),
                "non_finite": len(values) - len(finite),
                "negative": sum(1 for v in finite if v < 0),
                "min": min(finite) if finite else None,
                "max": max(finite) if finite else None,
            }
        )
    failures = {}
    for entry in rows:
        inputs = dict(zip(table["input_names"], entry["inputs"], strict=True))
        for gate in gates.failed(inputs, entry["raw"]):
            failures[gate] = failures.get(gate, 0) + 1
    return {
        "rows": len(rows),
        "width": widths,
        "expected_width": len(names),
        "columns": columns,
        "gate_failures": failures,
        "gates": list(gates.gate_names),
    }


def output_names(kind, version):
    if kind == "f08":
        from carbon.scoring import f08_dual_pack

        return list(f08_dual_pack._targets(version))
    from carbon.challenge_kit import physical_public_train
    from carbon.scoring import practice_grid

    chosen = practice_grid.adapter(kind, version)
    interface = physical_public_train.numeric_interface_document(chosen.CHALLENGE)
    return list(interface.get("output", {}).get("names", ()))


def report(result, print_=print) -> None:
    print_(
        f"rows {result['rows']}; width {result['width']} (interface: {result['expected_width']})"
    )
    print_("column                              values nonfinite negative  min .. max")
    for c in result["columns"]:
        span = "" if c["min"] is None else f"{c['min']:.6g} .. {c['max']:.6g}"
        print_(
            f"{c['name']:<36}{c['values']:>6} {c['non_finite']:>9} {c['negative']:>8}  {span}"
        )
    print_("physics gates (rows failing each; a gate not listed passes on every row):")
    for gate in result["gates"]:
        print_(
            f"   {gate:<34}{result['gate_failures'].get(gate, 0):>6} / {result['rows']}"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from carbon.scoring import pool_serving

    table = pool_serving.load_table(str(args.table))
    if (table.get("kind"), table.get("version")) != (args.kind, args.version):
        print(
            f"NOTE: the table is for {table.get('kind')} {table.get('version')}, "
            f"checked as {args.kind} {args.version}"
        )
    report(check(table, args.kind, args.version))
    return 0


if __name__ == "__main__":
    sys.exit(main())

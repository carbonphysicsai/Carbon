"""Run the photonic coupler pilot: typed reference records, refinements and the
closed-form baseline's errors.

    python scripts/dev/photonic/pilot.py OUTDIR --t20 T20.json --t5 T5.json
        [--tables carbon/photonic/tables_v1.json]

Cases, from public draws (`population.public_rng(LABEL)`):
- 8 ordinary draws of the DEVELOPMENT population;
- 4 difficult cases at the box's corners: the strongest coupler (smallest gap,
  longest), the weakest (largest gap, shortest), the shortest strong one,
  whose coupling is mostly in its bends, and the longest weak one.

Every case is evaluated from the reference tables (10 nm, full ladder), and
the reference checks it as `OK` or `REFERENCE_INVALID`:
- the integral converged: four times the z points changes the cross power by
  at most CHECKS["z_cross"] and the common phase by at most CHECKS["z_phase_rad"];
- the outputs pass the exam's gates, which the reference contract guarantees.

Every case also carries its refinement pairs, each against the reference
restricted to the same gaps, so each difference isolates one cause:
- `ladder`: every fourth gap against the full ladder (interpolation);
- `mesh_5nm`: the 5 nm table against the 10 nm one on every fourth gap;
- `mesh_20nm`: the 20 nm table likewise, for the observed order.
And the closed-form baseline's errors (`carbon.photonic.analytic`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.photonic import analytic, exam, population, reference

LABEL = "carbon.photonic.pilot-v1"
RECORD_SCHEMA = "carbon.photonic.reference-record.v1"
#: Provisional DEVELOPMENT reference checks: the midpoint rule's error at
#: 6,000 points is far below both (it is second order in a smooth profile).
CHECKS = {"z_cross": 1e-6, "z_phase_rad": 1e-4}
DIFFICULT = {
    "strongest": {"gap_nm": 150.0, "length_um": 6.0},
    "weakest": {"gap_nm": 300.0, "length_um": 1.0},
    "short-strong": {"gap_nm": 150.0, "length_um": 1.0},
    "long-weak": {"gap_nm": 300.0, "length_um": 6.0},
}


def plan():
    draws = population.draw(population.public_rng(LABEL), 8)
    cases = [
        {"case_id": f"ordinary-{i + 1}", "kind": "ordinary", "inputs": case}
        for i, case in enumerate(draws)
    ]
    cases += [
        {"case_id": name, "kind": "difficult", "inputs": inputs}
        for name, inputs in DIFFICULT.items()
    ]
    return {"batch": "photonic-pilot-v1", "label": LABEL, "cases": cases}


def subset(table, every):
    """The table restricted to every `every`-th gap of its ladder."""
    return table["gaps_um"][::every], {
        k: {"n_even": v["n_even"][::every], "n_odd": v["n_odd"][::every]}
        for k, v in table["wavelengths"].items()
    }


def difference(a, b):
    return {
        "cross_max": max(
            abs(x - y) for x, y in zip(a["cross_power"], b["cross_power"])
        ),
        "phase_max_rad": max(
            abs(x - y) for x, y in zip(a["common_phase_rad"], b["common_phase_rad"])
        ),
        "dphi_rel_max": max(
            abs(math.asin(math.sqrt(x)) / math.asin(math.sqrt(y)) - 1)
            for x, y in zip(a["cross_power"], b["cross_power"])
        ),
    }


def run_case(entry, tables, refinements):
    inputs = entry["inputs"]
    start = time.monotonic()
    outputs = reference.evaluate(inputs, tables)
    fine = reference.integrate(
        inputs, tables["gaps_um"], tables["wavelengths"], 4 * reference.Z_POINTS
    )
    z = difference(outputs, fine)
    reasons = []
    if z["cross_max"] > CHECKS["z_cross"]:
        reasons.append(f"z integral: cross power moved {z['cross_max']:.2e}")
    if z["phase_max_rad"] > CHECKS["z_phase_rad"]:
        reasons.append(f"z integral: phase moved {z['phase_max_rad']:.2e} rad")
    failed = [k for k, v in exam.gates(outputs).items() if v == exam.FAIL]
    if failed:
        reasons.append(f"reference fails gates {failed}")
    wall = time.monotonic() - start
    coarse = reference.integrate(inputs, *subset(tables, 4))
    refinement = {"z": z, "ladder": difference(coarse, outputs)}
    for name, table in refinements.items():
        refinement[name] = difference(
            reference.integrate(inputs, table["gaps_um"], table["wavelengths"]), coarse
        )
    record = {
        "schema": RECORD_SCHEMA,
        "case_id": entry["case_id"],
        "kind": entry["kind"],
        "inputs": inputs,
        "status": "REFERENCE_INVALID" if reasons else "OK",
        "reasons": reasons,
        "outputs": outputs,
        "wall_s": round(wall, 3),
        "refinement": refinement,
    }
    if not reasons:
        row = exam.score_case(
            analytic.predict(inputs), {"status": "OK", "outputs": outputs}
        )
        record["baseline_closed_form"] = row["errors"]
    return record


def summary(records, tables, refinements):
    ok = [r for r in records if r["status"] == "OK"]
    worst = {
        name: {
            key: max(r["refinement"][name][key] for r in records)
            for key in ("cross_max", "phase_max_rad", "dphi_rel_max")
        }
        for name in records[0]["refinement"]
    }
    order = {}
    if "mesh_5nm" in worst and "mesh_20nm" in worst:
        for key in ("phase_max_rad", "dphi_rel_max"):
            a, b = worst["mesh_20nm"][key], worst["mesh_5nm"][key]
            if a > 0 and b > 0:
                p = math.log(a / b) / math.log(2)
                order[key] = {
                    "observed_order": p,
                    # Richardson: the 10 nm table's remaining error is the
                    # 10-to-5 difference over 2^p - 1, plus that difference.
                    "estimated_10nm_error": b * 2**p / (2**p - 1) if p > 0 else None,
                }
    base = [r["baseline_closed_form"] for r in ok]
    return {
        "batch": "photonic-pilot-v1",
        "counts": {
            s: sum(1 for r in records if r["status"] == s)
            for s in sorted({r["status"] for r in records})
        },
        "worst_refinement": worst,
        "mesh_order": order,
        "baseline_closed_form": {
            key: {"min": min(b[key] for b in base), "max": max(b[key] for b in base)}
            for key in ("s_rms", "cross_rms", "phase_rms_rad", "cross_signed_centre")
        },
        "cross_power_range": [
            min(min(r["outputs"]["cross_power"]) for r in ok),
            max(max(r["outputs"]["cross_power"]) for r in ok),
        ],
        "tables": {
            "reference": tables["provenance"],
            **{name: t["provenance"] for name, t in refinements.items()},
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--tables", type=Path, default=reference.TABLES)
    parser.add_argument("--t20", type=Path, required=True)
    parser.add_argument("--t5", type=Path, required=True)
    args = parser.parse_args(argv)
    tables = reference.load_tables(args.tables)
    refinements = {}
    for name, path in (("mesh_5nm", args.t5), ("mesh_20nm", args.t20)):
        table = reference.load_tables(path)
        if table["status"] != "OK":
            raise SystemExit(f"{path} failed its checks: {table['reasons'][:3]}")
        if table["ladder"]["every"] == 1:
            gaps, rows = subset(table, 4)
            table = {**table, "gaps_um": gaps, "wavelengths": rows}
        if table["gaps_um"] != tables["gaps_um"][::4]:
            raise SystemExit(f"{path} is not on every fourth reference gap")
        refinements[name] = table
    args.out.mkdir(parents=True, exist_ok=True)
    p = plan()
    (args.out / "plan.json").write_text(json.dumps(p, indent=2) + "\n")
    records = [run_case(entry, tables, refinements) for entry in p["cases"]]
    with (args.out / "records.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    report = summary(records, tables, refinements)
    report["tables_sha256"] = {
        "reference": hashlib.sha256(Path(args.tables).read_bytes()).hexdigest(),
        "mesh_5nm": hashlib.sha256(args.t5.read_bytes()).hexdigest(),
        "mesh_20nm": hashlib.sha256(args.t20.read_bytes()).hexdigest(),
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["counts"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

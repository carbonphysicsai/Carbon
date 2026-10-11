"""#965 middle-band panel refinement plans: rung 2 and the conditional rung 3
(EVIDENCE-PRODUCER-STAGES-01).

    python scripts/dev/battery/middle_bands_refine.py rung2 RUNS OUT.json
    python scripts/dev/battery/middle_bands_refine.py rung3 RUNS OUT.json

The panel's section 7 (`question-laws/battery-v3-middle-bands-panel.md`)
registers the rule; this module only applies it to the accepted manifest
(bab5ae97) and the solved records under RUNS, deterministically:

- **Relevance.** A tuple is relevant when its standard result lies within
  TWO working bands of any requirement the export draws: the temperature cap
  ranges over [42.5, 45] C (margin U[0, 2.5] K) and the plating floor over
  [0, 2] mV (margin U[0, 2] mV), so the windows are [41.5, 46.0] C and
  [-4, 6] mV with bands 0.5 K and 2 mV.
- **Rung 2.** Each relevant tuple without a matching rung-2 record gets the
  registered refined re-solve (mesh 40, rtol 1e-6, atol 1e-8): at most one
  per tuple. Existing rung-2 records are reused by physical identity.
- **Rung 3.** Only for a relevant tuple whose standard and rung-2 values
  straddle a drawn limit or differ by at least the band, without a rung-3
  record. Ranked by the rung-2 distance to the nominal limit in bands, then
  manifest order; the stage-A ceiling is 60. The rest stay UNRESOLVED.
- No automatic retries. A tuple without a standard OK record is reported, not
  planned.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import feasibility02_v2 as v2
import middle_bands as mb

MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "docs/development/evidence/battery-feasibility-02/middle-bands/manifest.json"
)
MANIFEST_SHA256 = "bab5ae9702dc0a8ec3c8f26b9ddd9337c19152dc4d1f8692c3bc8d33c14f7e39"
STAGE_A_DIR, RUNG2_DIR, RUNG3_DIR = "bmid-a", "bmid-r2", "bmid-r3"
STANDARD_DIRS = (*mb.RUNG_DIRS["standard_and_rung2"], STAGE_A_DIR, RUNG2_DIR)
RUNG3_DIRS = (*mb.RUNG_DIRS["rung3"], RUNG3_DIR)
#: (quantity, drawn limit range, band): cap 45 - U[0, 2.5] K; floor U[0, 2] mV
LIMITS = (
    ("charging_t_max_c", (42.5, 45.0), v2.T_BAND_C),
    ("plating_min_v", (0.0, 0.002), v2.PLATING_BAND_V),
)
NOMINAL = {"charging_t_max_c": 45.0, "plating_min_v": 0.0}
NEAR_BANDS = 2
RUNG3_CEILING = 60


def tuples():
    body = json.loads(MANIFEST.read_text())
    if body["manifest_sha256"] != MANIFEST_SHA256:
        raise SystemExit("middle-band manifest differs from the accepted one")
    return body["tuples"]


def _key(row):
    return mb._key(row["c1"], row["c2"], row["cooling"], row["ambient_c"])


def solved(runs):
    """{key: {rung: measures}} over every OK record at SOC0 0.10."""
    out = {}
    for rung_dirs, rung3 in ((STANDARD_DIRS, False), (RUNG3_DIRS, True)):
        for name in rung_dirs:
            path = Path(runs) / name / "records.jsonl"
            if not path.exists():
                continue
            for line in path.read_text().splitlines():
                r = json.loads(line) if line.strip() else None
                if (
                    not r
                    or r["status"] != "OK"
                    or r["case_id"].startswith("control-")
                    or r.get("soc0", 0.1) != 0.1
                ):
                    continue
                k = mb._key(r["c1"], r["c2"], r["h_multiplier"], r["t_amb_c"],
                            r.get("switch_voltage_v", 4.0))  # fmt: skip
                rung = (
                    "rung3"
                    if rung3
                    else "rung2" if r["case_id"].startswith("refined:") else "standard"
                )
                out.setdefault(k, {}).setdefault(rung, v2.measures(r))
    return out


def relevant(measures):
    for quantity, (lo, hi), band in LIMITS:
        value = measures[quantity]
        if (
            value is not None
            and lo - NEAR_BANDS * band <= value <= hi + NEAR_BANDS * band
        ):
            return True
    return False


def needs_rung3(std, r2):
    for quantity, (lo, hi), band in LIMITS:
        a, b = std[quantity], r2[quantity]
        if a is None or b is None:
            continue
        low, high = min(a, b), max(a, b)
        if abs(a - b) >= band or (low < hi and high >= lo and low != high):
            return True
    return False


def _job(row, prefix, rung):
    job = {"case_id": f"{prefix}t7:{row['id']}", "c1": float(row["c1"]), "c2": float(row["c2"]),
           "t_amb_c": float(row["ambient_c"]), "soc0": 0.1, "h_multiplier": float(row["cooling"]),
           "switch_voltage_v": 4.0, "refined": True}  # fmt: skip
    if rung == 3:
        job["rung"] = 3
    return job


def plan(runs, rung):
    have = solved(runs)
    jobs, absent, ranked = [], [], []
    for order, row in enumerate(tuples()):
        found = have.get(_key(row), {})
        std = found.get("standard")
        if std is None:
            absent.append(row["id"])
            continue
        if not relevant(std):
            continue
        if rung == 2 and "rung2" not in found:
            jobs.append(_job(row, "refined:", 2))
        if rung == 3 and "rung2" in found and "rung3" not in found:
            r2 = found["rung2"]
            if needs_rung3(std, r2):
                distance = min(
                    abs(r2[q] - NOMINAL[q]) / band
                    for q, _, band in LIMITS
                    if r2[q] is not None
                )
                ranked.append((distance, order, row))
    if rung == 3:
        jobs = [_job(row, "rung3:", 3) for _, _, row in sorted(ranked)[:RUNG3_CEILING]]
    batch = f"battery-v3-middle-bands-rung{rung}"
    return {"batch": batch, "pr": "#965", "jobs": jobs}, {
        "planned": len(jobs),
        "standard_absent": absent,
        "rung3_candidates": len(ranked) if rung == 3 else None,
    }


def main(argv=None):
    cmd, runs, out = (argv or sys.argv[1:])[:3]
    body, summary = plan(runs, {"rung2": 2, "rung3": 3}[cmd])
    Path(out).write_text(json.dumps(body, indent=1) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()

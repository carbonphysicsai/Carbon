#!/usr/bin/env python3
"""Battery B15: a public DEVELOPMENT probe plan for the exposed bank.

The adopted B15 gate (OWNER-PHYSICS-GATES-01, `carbon.battery.physics_gate`)
reads one registered probe plan, and none is committed, so the gate cannot run
on the exposed DEVELOPMENT bank. B15 was screened on PHYSICS-CALIBRATION-01's
public plan (`physcal_plan.py`, seed `physics-calibration-01`, 100 bases, plan
sha256 83d7ddce...; `physics-screen-pairs.json` pair_cache_provenance). This
is that generator under a new public seed:

- 100 base points drawn uniformly from the contract's probe region, each
  coordinate kept below its upper edge by the largest move the screen plan
  made along it (from the screen plan's own `moves`), in the same draw order;
- for each base, one c1 and one c2 partner moved up by B15's 0.05 step.

So 200 pairs, 100 per axis, as the gate was screened at. No references are
needed: the gate reads only model predictions on the pairs. The sealed exam
keeps a private draw. The plan file has exactly the gate's three fields, so
the seed, counts, the disjointness check against the screen plan and the
plan's sha256 live in the sidecar provenance file.

    python3 scripts/dev/battery/b15_public_probes.py OUT_DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))

from carbon.battery import physics_gate as gate

PUBLIC_SEED = "carbon-battery-b15-public-development-20261020"
BASES = 100
PROVENANCE_SCHEMA = "carbon.battery.physics-probes-public-provenance.v1"
EVIDENCE = "docs/development/evidence/battery-b15-public-probes-20261020"
#: The public plan B15 was screened on, and its job inputs (both public).
SCREEN_PLAN = (
    EVIDENCE + "/screen-plan-physics-calibration-01.json",
    "83d7ddce8a7e260fe2e0f19968b045abf15b522fa7d2df61b7fb0d3567ac6fdf",
)
SCREEN_JOBS = (
    EVIDENCE + "/screen-jobs-physics-calibration-01.json",
    "eebb8066d60af75fc3cf0f71e65885688da35da16c99313e7f846ccdf1c98308",
)


def _pinned(path_and_sha):
    raw = (REPOSITORY / path_and_sha[0]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != path_and_sha[1]:
        raise SystemExit(f"refused: {path_and_sha[0]} differs from its pin")
    return raw


def _contract():
    raw = (REPOSITORY / gate.CONTRACT).read_bytes()
    return raw, json.loads(raw)


def bases(seed: str, count: int = BASES) -> list[dict]:
    """The screen generator's base draw (`physcal_plan.py`), seed `seed`."""
    screen = json.loads(_pinned(SCREEN_PLAN))
    region = screen["contract"]["probe_region"]
    names = sorted(region)
    headroom = {
        n: max(m["step_fraction"] for m in screen["moves"] if m["input"] == n)
        for n in names
    }
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        out.append(
            {
                n: rng.uniform(
                    region[n][0],
                    region[n][1] - headroom.get(n, 0.0) * (region[n][1] - region[n][0]),
                )
                for n in names
            }
        )
    return out


def _screen_points():
    """Every input point and every c1/c2 0.05 pair of the screen plan."""
    jobs = {j["case_id"]: j for j in json.loads(_pinned(SCREEN_JOBS))["jobs"]}
    screen = json.loads(_pinned(SCREEN_PLAN))
    names = sorted(screen["contract"]["probe_region"])
    points = {tuple(job[n] for n in names) for job in jobs.values()}
    pairs = {
        (
            pair["input"],
            *(jobs[pair["base"]][n] for n in names),
            *(jobs[pair["partner"]][n] for n in names),
        )
        for pair in screen["pairs"]
        if pair["step_fraction"] == 0.05 and pair["input"] in ("c1", "c2")
    }
    return names, points, pairs


def plan() -> tuple[bytes, dict]:
    """The public plan bytes and their provenance (deterministic)."""
    raw, contract = _contract()
    law = next(law for law in contract["laws"] if law["id"] == "B15")
    region = contract["probe_region"]
    pairs = []
    for base in bases(PUBLIC_SEED):
        for axis in law["inputs"]:
            step = law["step"] * (region[axis][1] - region[axis][0])
            pairs.append(
                {
                    "axis": axis,
                    "base": dict(base),
                    "partner": {**base, axis: base[axis] + step},
                }
            )
    body = {
        "schema": gate.PROBE_SCHEMA,
        "contract_sha256": hashlib.sha256(raw).hexdigest(),
        "pairs": pairs,
    }
    plan_raw = json.dumps(body, sort_keys=True, indent=1).encode() + b"\n"
    names, screen_points, screen_pairs = _screen_points()
    ours_points = {
        tuple(p[s][n] for n in names) for p in pairs for s in ("base", "partner")
    }
    ours_pairs = {
        (p["axis"], *(p["base"][n] for n in names), *(p["partner"][n] for n in names))
        for p in pairs
    }
    provenance = {
        "schema": PROVENANCE_SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT_ONLY",
        "law": "B15",
        "contract": gate.CONTRACT,
        "contract_sha256": body["contract_sha256"],
        "generator": "PHYSICS-CALIBRATION-01 physcal_plan.py base draw, B15 c1/c2 moves",
        "seed": PUBLIC_SEED,
        "bases": BASES,
        "pairs": len(pairs),
        "axes": {a: sum(p["axis"] == a for p in pairs) for a in law["inputs"]},
        "screened_at": {
            "plan_sha256": SCREEN_PLAN[1],
            "jobs_sha256": SCREEN_JOBS[1],
            "seed": json.loads(_pinned(SCREEN_PLAN))["seed"],
            "pairs_per_base": BASES,
        },
        "disjoint_from_screen": {
            "checked": True,
            "shared_pairs": len(ours_pairs & screen_pairs),
            "shared_points": len(ours_points & screen_points),
        },
        "plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
        "references_needed": False,
        "sealed_exam": "keeps its private draw; this plan is not it",
    }
    if provenance["disjoint_from_screen"]["shared_points"]:
        raise SystemExit("refused: the public plan shares a point with the screen plan")
    return plan_raw, provenance


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", type=Path)
    args = parser.parse_args(argv)
    plan_raw, provenance = plan()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "plan.json").write_bytes(plan_raw)
    (args.out / "provenance.json").write_bytes(
        json.dumps(provenance, sort_keys=True, indent=1).encode() + b"\n"
    )
    print(json.dumps({k: provenance[k] for k in ("pairs", "axes", "plan_sha256")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

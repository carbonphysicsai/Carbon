"""PRACTICE-SAFETY-01 B4: the battery practice decision set (public).

    python -m scripts.dev.battery.practice_decision_set select
    python -m scripts.dev.battery.practice_decision_set jobs --out JOBS.json

The selection rule is fixed here and committed before any solve (the Test
Lead's ruling, 2026-10-05):
- six conditions inside the published box (t_amb 5–40 °C, soc0 0.05–0.50):
  four representative ones drawn uniformly over the box, and two near-limit
  ones drawn from low t_amb and high soc0 (t_amb 5–12 °C, soc0 0.38–0.50);
- a draw is refused only when it lies within BOTH 2 °C in t_amb AND 0.03 in
  soc0 of an EV1, EV2, EV4 or EV5 condition, a point of EV4's protected
  optimizer grid, or a condition already chosen;
- draws come from numpy PCG64 seeded with the first 8 bytes of
  sha256("PRACTICE-SAFETY-01-B4"); t_amb is rounded to 0.1 °C and soc0 to
  0.001, before the refusal test.

Each condition is solved at EV4's 35-candidate grid (210 public solves on
the operator host). Once published, these six conditions are permanently
practice-only: never Track B, never a confirmation set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = "docs/development/evidence/practice-decision-set-v1"
EVIDENCE_V2 = "docs/development/evidence/practice-decision-set-v2"
SEED_LABEL_V2 = "PRACTICE-SAFETY-01-B4-v2"
SEED_LABEL = "PRACTICE-SAFETY-01-B4"
BOX = {"t_amb_c": (5.0, 40.0), "soc0": (0.05, 0.50)}
NEAR_LIMIT = {"t_amb_c": (5.0, 12.0), "soc0": (0.38, 0.50)}
REPRESENTATIVE, NEAR = 4, 2
MIN_T, MIN_SOC = 2.0, 0.03
CONTRACT = "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"


def excluded():
    """Every condition the set must keep its distance from."""
    from carbon.battery.value import ev5

    points = []
    for values in ev5.prior_conditions().values():
        points += [tuple(map(float, p)) for p in values]
    for values in ev5.conditions().values():
        points += [tuple(map(float, p)) for p in values]
    return sorted(set(points))


def excluded_v2():
    """v2's wider list (Test Lead ruling, 2026-10-06: EV5's protected grids
    count as EV5): every EV4 and EV5 protected grid (development,
    verification, model, optimizer verification) and every committed
    contract's decision conditions, as #652's separation check reads them."""
    from carbon.battery.value import ev4_protected_conditions as ev4
    from carbon.battery.value import ev5_protected_conditions as ev5

    grids = (
        ev4.EV4_DEVELOPMENT,
        ev4.EV4_VERIFICATION,
        ev4.EV4_MODEL,
        ev4.EV4_OPTIMIZER_VERIFICATION,
        ev5.EV5_DEVELOPMENT,
        ev5.EV5_VERIFICATION,
        ev5.EV5_MODEL,
        ev5.EV5_OPTIMIZER_VERIFICATION,
    )
    points = {(float(t), float(s)) for grid in grids for t, s in grid}
    for path in sorted((ROOT / "carbon/battery/value/contracts").glob("*.json")):
        scenarios = json.loads(path.read_text())["scenarios"]
        for role in ("development", "verification"):
            for scenario in scenarios[role]:
                points |= {(float(t), float(s)) for t, s in scenario["conditions"]}
    return sorted(points)


def select_v2(prior=None):
    """v2: v1's conditions that keep their distance from the wider list stay;
    each that does not is redrawn, same kind and region, from the v2 seed,
    under the same refusal rule (against the wider list and every kept or
    new condition)."""
    prior = excluded_v2() if prior is None else prior
    v1 = json.loads((ROOT / EVIDENCE / "conditions.json").read_text())["conditions"]
    kept = [c for c in v1 if not refused((c["t_amb_c"], c["soc0"]), prior)]
    dropped = [c for c in v1 if c not in kept]
    seed = int.from_bytes(hashlib.sha256(SEED_LABEL_V2.encode()).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    chosen = list(kept)
    regions = {"representative": BOX, "near_limit": NEAR_LIMIT}
    for old in dropped:
        while True:
            point = _draw(rng, regions[old["kind"]])
            taken = [(c["t_amb_c"], c["soc0"]) for c in chosen]
            if not refused(point, prior + taken):
                break
        chosen.append(
            {
                "id": f"P-T{point[0]:g}-S{point[1]:g}",
                "kind": old["kind"],
                "t_amb_c": point[0],
                "soc0": point[1],
                "replaces": old["id"],
            }
        )
    return {
        "schema": "carbon.battery.practice-decision-set.v2",
        "rule": (
            "v1's rule (scripts/dev/battery/practice_decision_set.py) against the "
            "wider exclusion list (excluded_v2); v1 conditions that stay clear "
            "are kept, the rest redrawn with seed label " + SEED_LABEL_V2
        ),
        "seed_label": SEED_LABEL_V2,
        "excluded_points": len(prior),
        "supersedes": "practice-decision-set-v1 (two conditions within both "
        "bounds of EV5 protected grid points; Test Lead ruling 2026-10-06)",
        "conditions": chosen,
        "status": "PRACTICE_ONLY: never Track B, never a confirmation set",
    }


def refused(point, others):
    """Within BOTH distances of any other point."""
    t, s = point
    return any(abs(t - ot) < MIN_T and abs(s - os) < MIN_SOC for ot, os in others)


def _draw(rng, region):
    t = round(float(rng.uniform(*region["t_amb_c"])), 1)
    s = round(float(rng.uniform(*region["soc0"])), 3)
    return t, s


def select(prior=None):
    prior = excluded() if prior is None else prior
    seed = int.from_bytes(hashlib.sha256(SEED_LABEL.encode()).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    chosen = []
    for kind, region, count in (
        ("representative", BOX, REPRESENTATIVE),
        ("near_limit", NEAR_LIMIT, NEAR),
    ):
        taken = 0
        while taken < count:
            point = _draw(rng, region)
            if refused(point, prior + [(c["t_amb_c"], c["soc0"]) for c in chosen]):
                continue
            chosen.append(
                {
                    "id": f"P-T{point[0]:g}-S{point[1]:g}",
                    "kind": kind,
                    "t_amb_c": point[0],
                    "soc0": point[1],
                }
            )
            taken += 1
    return {
        "schema": "carbon.battery.practice-decision-set.v1",
        "rule": __doc__.split("The selection rule")[1]
        .split("Each condition")[0]
        .strip(),
        "seed_label": SEED_LABEL,
        "excluded_points": len(prior),
        "conditions": chosen,
        "status": "PRACTICE_ONLY: never Track B, never a confirmation set",
    }


def jobs(document):
    """The 210 public solves: each condition at EV4's 35 candidates."""
    from carbon.battery.value import contract as ev

    contract, _ = ev.load(ROOT / CONTRACT)
    out = []
    for condition in document["conditions"]:
        for candidate in ev.candidates(contract):
            c1, c2 = candidate["c1"], candidate["c2"]
            out.append(
                {
                    "case_id": f"practice-b4-{condition['id']}-c1{c1:g}-c2{c2:g}",
                    "c1": float(c1),
                    "c2": float(c2),
                    "t_amb_c": condition["t_amb_c"],
                    "soc0": condition["soc0"],
                }
            )
    return {"fingerprint": "public-practice-b4-v1", "jobs": out}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="practice_decision_set")
    parser.add_argument("command", choices=("select", "jobs", "select-v2", "jobs-v2"))
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    if args.command in ("select-v2", "jobs-v2"):
        path = ROOT / EVIDENCE_V2 / "conditions.json"
        if args.command == "select-v2":
            path.parent.mkdir(parents=True, exist_ok=True)
            document = select_v2()
            path.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
            print(json.dumps(document["conditions"]))
            return 0
        document = json.loads(path.read_text())
        new = {
            **document,
            "conditions": [c for c in document["conditions"] if "replaces" in c],
        }
        Path(args.out).write_text(json.dumps(jobs(new), indent=1) + "\n")
        print(json.dumps({"jobs": len(jobs(new)["jobs"])}))
        return 0
    path = ROOT / EVIDENCE / "conditions.json"
    if args.command == "select":
        path.parent.mkdir(parents=True, exist_ok=True)
        document = select()
        path.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
        print(json.dumps(document["conditions"]))
        return 0
    document = json.loads(path.read_text())
    Path(args.out).write_text(json.dumps(jobs(document), indent=1) + "\n")
    print(json.dumps({"jobs": len(jobs(document)["jobs"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

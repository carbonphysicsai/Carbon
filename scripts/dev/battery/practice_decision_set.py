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
    parser.add_argument("command", choices=("select", "jobs"))
    parser.add_argument("--out")
    args = parser.parse_args(argv)
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

"""Write the #344 reference pilot's plan: 8 ordinary, 4 difficult, 4 refined.

    python scripts/dev/motor/reference/pilot_plan.py OUT.json

Rules stated before they are applied; every draw is public
(`population.public_rng`):

- **Ordinary:** the first 8 admitted draws of the population.
- **Difficult:** from 4,000 further admitted draws, the one maximizing each
  score in turn, without repeating a case:
  1. `deep-saturation`: ampere-turns per tooth width, J * coil area / tooth;
  2. `sharpest-cogging`: slot opening over airgap;
  3. `weakest-field`: airgap over magnet thickness;
  4. `field-weakening`: current density * sin(current angle), the
     demagnetizing d-axis current (the magnets are linear: demagnetization
     is outside the model, and this case marks that edge).
- **Refined:** ordinary 1 and 2 and difficult 1 and 2 again at 2,880 airgap
  nodes (rung M1's finest mesh), at every 1 degree over the full period,
  paired with their 1,440-node runs at the same angles.
- **Angle refinement:** ordinary 2 at 0.125 degree positions on the refined
  mesh over the first 3.75 degrees, against its 0.25 degree curve.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.motor import domain, population

LABEL = "carbon.motor.pilot-v1"
DIFFICULT = (
    (
        "deep-saturation",
        lambda c: c["current_density_a_mm2"] * domain.coil_area_mm2(c) / c["tooth_mm"],
    ),
    ("sharpest-cogging", lambda c: c["slot_open_deg"] / c["airgap_mm"]),
    ("weakest-field", lambda c: c["airgap_mm"] / c["magnet_mm"]),
    (
        "field-weakening",
        lambda c: (
            c["current_density_a_mm2"] * math.sin(math.radians(c["current_angle_deg"]))
        ),
    ),
)


def plan():
    ordinary, ordinary_draws = population.draw(
        population.public_rng(LABEL + ".ordinary"), 8
    )
    candidates, candidate_draws = population.draw(
        population.public_rng(LABEL + ".difficult"), 4000
    )
    chosen, used = [], set()
    for name, score in DIFFICULT:
        index = max(
            (i for i in range(len(candidates)) if i not in used),
            key=lambda i: score(candidates[i]),
        )
        used.add(index)
        chosen.append((name, candidates[index]))
    cases = [
        {"case_id": f"ordinary-{i + 1}", "kind": "ordinary", "inputs": c}
        for i, c in enumerate(ordinary)
    ] + [
        {"case_id": f"difficult-{i + 1}-{name}", "kind": "corner", "inputs": c}
        for i, (name, c) in enumerate(chosen)
    ]
    refined = [cases[0], cases[1], cases[8], cases[9]]
    fine = {"n_gap": 2 * domain.N_GAP, "h_max": domain.H_MAX_MM / 2}
    cases += [
        {
            "case_id": c["case_id"] + "-n2880",
            "kind": "refinement",
            "inputs": c["inputs"],
            # Every 1 degree (every 4th base position) over the full period:
            # the refined mesh costs about 4x per position.
            "options": {**fine, "angle_steps": 15},
            "pairs_with": c["case_id"],
        }
        for c in refined
    ]
    cases.append(
        {
            "case_id": "ordinary-2-n2880-a120",
            "kind": "diagnostic",
            "inputs": cases[1]["inputs"],
            # Angle refinement: 0.125 degree positions on the refined mesh,
            # over the first 3.75 degrees.
            "options": {**fine, "angle_steps": 120, "positions": 31},
            "pairs_with": "ordinary-2",
        }
    )
    return {
        "batch": "motor-pilot-v1",
        "population": population.POPULATION_VERSION,
        "label": LABEL,
        "draws": {"ordinary": ordinary_draws, "difficult": candidate_draws},
        "cases": cases,
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        raise SystemExit(__doc__)
    Path(argv[0]).write_text(json.dumps(plan(), indent=2) + "\n")
    print(argv[0])


if __name__ == "__main__":
    main()

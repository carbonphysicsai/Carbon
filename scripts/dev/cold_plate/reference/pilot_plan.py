"""Write the #342 reference pilot's plan: 8 ordinary, 4 difficult, 4 refined.

    python scripts/dev/cold_plate/reference/pilot_plan.py OUT.json

#342 asks for 8 ordinary and 4 difficult valid cases with paired refinement
of at least 4: an engineering pilot count, not statistical sufficiency. Every
choice below is a rule stated here before it is applied, and every draw is
public and reproducible (`population.public_rng`):

- **Ordinary:** the first 8 admitted draws of the population.
- **Difficult:** from 4,000 further admitted draws, the one that maximizes
  each of these, in turn, without repeating a case:
  1. `screen-edge`: the closed-form hottest wall. It tests the screen's
     margin: the reference's own fluid must stay at or below 99 C.
  2. `sharpest-spot`: the hot spot's peak flux over its width,
     ratio * heat load / width. Base spreading matters most here, which the
     closed-form model ignores, and the mesh must resolve the spot.
  3. `highest-pressure`: the closed-form pressure drop.
  4. `highest-re`: the closed-form Reynolds number: the longest developing
     flow.
- **Refined:** ordinary 1 and 2 and difficult 1 and 2 again at resolution 3
  (rung 5b's refinement), paired with their resolution-2 runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.cold_plate import analytic, population

LABEL = "carbon.cold-plate.pilot-v1"
DIFFICULT = (
    ("screen-edge", lambda case, r: r["diagnostics"]["max_wall_c"]),
    (
        "sharpest-spot",
        lambda case, r: case["hotspot_ratio"]
        * case["heat_load_w"]
        / case["hotspot_width_mm"],
    ),
    ("highest-pressure", lambda case, r: r["pressure_drop_pa"]),
    ("highest-re", lambda case, r: r["diagnostics"]["re_max"]),
)


def plan():
    ordinary, ordinary_draws = population.draw(
        population.public_rng(LABEL + ".ordinary"), 8
    )
    candidates, candidate_draws = population.draw(
        population.public_rng(LABEL + ".difficult"), 4000
    )
    scored = [(case, analytic.predict(case)) for case in candidates]
    chosen, used = [], set()
    for name, key in DIFFICULT:
        index = max(
            (i for i in range(len(scored)) if i not in used),
            key=lambda i: key(*scored[i]),
        )
        used.add(index)
        chosen.append((name, scored[index][0]))
    cases = [
        {"case_id": f"ordinary-{i + 1}", "kind": "ordinary", "inputs": case}
        for i, case in enumerate(ordinary)
    ] + [
        {"case_id": f"difficult-{i + 1}-{name}", "kind": "corner", "inputs": case}
        for i, (name, case) in enumerate(chosen)
    ]
    refined = [cases[0], cases[1], cases[8], cases[9]]
    cases += [
        {
            "case_id": c["case_id"] + "-r3",
            "kind": "refinement",
            "inputs": c["inputs"],
            "options": {"resolution": 3},
            "pairs_with": c["case_id"],
        }
        for c in refined
    ]
    return {
        "batch": "pilot-v1",
        "population": population.POPULATION_VERSION,
        "screen": population.SCREEN,
        "label": LABEL,
        "draws": {"ordinary": ordinary_draws, "difficult": candidate_draws},
        "cases": cases,
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        raise SystemExit(__doc__)
    out = Path(argv[0])
    out.write_text(json.dumps(plan(), indent=2) + "\n")
    print(out)


if __name__ == "__main__":
    main()

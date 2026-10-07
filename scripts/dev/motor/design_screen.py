"""motor-design-tasks-v1: the public screening and repeatability plans.

    python -m scripts.dev.motor.design_screen plan --out DIR

Writes `screen-plan.json` (30 public geometries x study V2's six conditions)
and `repeat-plan.json` (the 20 public TRAIN/PRACTICE cases nearest a limit,
re-solved refined), both in `run_batch.py`'s plan format. Draws come from the
DEVELOPMENT population's public generator; no exam material is read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

V2 = ROOT / "docs/development/studies/MOTOR_SYNTHETIC_DECISION_V2.json"
POOLS = ROOT / "docs/development/evidence/motor-pools-v1"
LIMIT_T, LIMIT_R = 4.0, 0.30
BAND_T, BAND_R = 0.4, 0.03
GEOMETRY = (
    "magnet_mm",
    "embrace",
    "airgap_mm",
    "slot_open_deg",
    "tooth_mm",
    "slot_bottom_mm",
)
REFINED = {"n_gap": 2880, "h_max": 0.5}


def derived(torque):
    values = list(torque)
    mean = sum(values) / len(values)
    return mean, max(values) - min(values)


def distance(mean, ripple):
    """Distance to the nearer limit, in near bands."""
    rf = ripple / abs(mean) if mean else float("inf")
    return min(abs(mean - LIMIT_T) / BAND_T, abs(rf - LIMIT_R) / BAND_R)


def conditions():
    return json.loads(V2.read_text())["conditions"]


def geometries():
    from carbon.motor import decision_study, population

    rng = population.public_rng("MOTOR-SCREEN-V1")
    uniform, _ = population.draw(rng, 15)
    pool, _ = population.draw(rng, 2000)
    config = json.loads(V2.read_text())
    models, _ = decision_study.reconstruct_models(config, repository=ROOT)
    krr = models["learned-krr-v1"]
    conds = conditions()

    def near(case):
        rows = {
            c["condition_id"]: {
                **{k: case[k] for k in GEOMETRY},
                **c["values"],
            }
            for c in conds
        }
        out = krr(rows)
        return min(distance(*derived(out[c]["torque_nm"])) for c in out)

    ranked = sorted(range(len(pool)), key=lambda i: (near(pool[i]), i))[:15]
    picks = [("uniform", g) for g in uniform] + [("near", pool[i]) for i in ranked]
    return [(s, {k: g[k] for k in GEOMETRY}) for s, g in picks]


def plan(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cases, designs = [], []
    for n, (stratum, geometry) in enumerate(geometries()):
        gid = f"g{n:02d}"
        designs.append({"design_id": gid, "drawn": stratum, "values": geometry})
        for c in conditions():
            cases.append(
                {
                    "case_id": f"screen-{gid}-{c['condition_id']}",
                    "kind": "ordinary",
                    "inputs": {**geometry, **c["values"]},
                }
            )
    (out / "screen-plan.json").write_text(
        json.dumps(
            {"batch": "motor-design-screen-v1", "designs": designs, "cases": cases},
            indent=1,
        )
        + "\n"
    )
    pooled = []
    for name in ("train.jsonl", "practice.jsonl"):
        for line in (POOLS / name).read_text().splitlines():
            r = json.loads(line)
            if r.get("status") == "OK":
                d = r["derived"]
                pooled.append(
                    (distance(d["mean_nm"], d["ripple_pk_pk_nm"]), name, r)
                )
    pooled.sort(key=lambda t: (t[0], t[1], t[2]["case_id"]))
    repeat = [
        {
            "case_id": f"repeat-{name.split('.')[0]}-{r['case_id']}",
            "kind": "refinement",
            "inputs": r["inputs"],
            "options": REFINED,
        }
        for _d, name, r in pooled[:20]
    ]
    (out / "repeat-plan.json").write_text(
        json.dumps({"batch": "motor-design-repeat-v1", "cases": repeat}, indent=1)
        + "\n"
    )
    return {"screen_cases": len(cases), "repeat_cases": len(repeat)}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="design_screen")
    parser.add_argument("command", choices=("plan",))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(plan(args.out), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

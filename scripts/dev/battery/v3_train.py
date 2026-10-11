"""Battery v3 public TRAIN set (registry battery-feasibility-02/v3-train-registry.json).

    python scripts/dev/battery/v3_train.py MANIFEST.json RUNS OUT_PLAN.json

Test Lead 2026-10-10: Carbon's battery kit cannot express v3's actions
(switch voltage, cooling level, c1 below 0.5), so no Carbon model can be
trained for v3 evidence. This draws a seeded public TRAIN set over the v3
action and context space, disjoint from the #965 middle-band manifest and
from every solved study record, with the same records (all 30 cycles,
per-phase extrema, every-charge plating, SOC clock) so the labels reduce to
the panel observables.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import middle_bands as mb

SIZE, SEED = 4000, 20261010
SWITCH_V = (4.00, 4.05, 4.10, 4.15)
COOLING = (1.0, 2.0, 4.0)
SOC0 = (0.10, 0.20, 0.30)


def draw(manifest, runs):
    taken = {
        mb._key(t["c1"], t["c2"], t["cooling"], t["ambient_c"]) + (0.1,)
        for t in manifest["tuples"]
    }
    taken |= {k + (0.1,) for k in mb.solved(runs)}
    rng = np.random.default_rng(SEED)
    jobs, seen = [], set()
    while len(jobs) < SIZE:
        c1 = round(float(rng.uniform(0.25, 2.0)), 2)
        c2 = round(float(rng.uniform(0.25, c1)), 2)
        sv = SWITCH_V[int(rng.integers(len(SWITCH_V)))]
        h = COOLING[int(rng.integers(len(COOLING)))]
        t = round(float(rng.uniform(5.0, 40.0)) * 2) / 2
        soc = SOC0[int(rng.integers(len(SOC0)))]
        key = mb._key(c1, c2, h, t, sv) + (soc,)
        if c2 > c1 or key in taken or key in seen:
            continue
        seen.add(key)
        jobs.append({"case_id": f"v3train:c1={c1:.2f}:c2={c2:.2f}:sv={sv:.2f}:h{h:g}:T{t:g}:SOC={soc:.2f}",
                     "c1": c1, "c2": c2, "t_amb_c": t, "soc0": soc, "h_multiplier": h,
                     "switch_voltage_v": sv, "refined": False})  # fmt: skip
    return jobs


if __name__ == "__main__":
    manifest = json.loads(Path(sys.argv[1]).read_text())
    jobs = draw(manifest, sys.argv[2])
    body = {
        "batch": "battery-v3-train-v1",
        "role": "PUBLIC_TRAIN",
        "seed": SEED,
        "jobs": jobs,
    }
    text = json.dumps(body, sort_keys=True, separators=(",", ":"))
    Path(sys.argv[3]).write_text(text + "\n")
    print(
        json.dumps(
            {
                "jobs": len(jobs),
                "plan_sha256": hashlib.sha256((text + "\n").encode()).hexdigest(),
            }
        )
    )

"""Campaign plans: case lists per role with seeds derived from one campaign root.

Seeds are ``sha256(CAMPAIGN_ROOT + "/" + role)`` truncated to 32 bits, so every
role draws from an independent stream. Independent seeds are not semantic
decontamination: every role samples the same uniform input distribution, so the
report states nearest-neighbour distances between roles rather than claiming
the roles are disjoint in content.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from scripts.dev.exam_design.battery_reference import SPEC

CAMPAIGN_ROOT = "carbon.exam-design.battery.2026-09-24"


def role_seed(role: str) -> int:
    return int(hashlib.sha256(f"{CAMPAIGN_ROOT}/{role}".encode()).hexdigest()[:8], 16)


def lhs_cases(n: int, role: str, prefix: str) -> list[dict]:
    """Latin-hypercube draws over the declared bounds (used for small, varied pilot sets)."""
    rng = np.random.default_rng(role_seed(role))
    b = SPEC["input_bounds"]
    cols = {}
    for k, (lo, hi) in b.items():
        u = (rng.permutation(n) + rng.uniform(size=n)) / n
        cols[k] = lo + u * (hi - lo)
    return [{"case_id": f"{prefix}-{i:04d}", **{k: float(np.round(cols[k][i], 4)) for k in b}} for i in range(n)]


def uniform_cases(n: int, role: str, prefix: str) -> list[dict]:
    rng = np.random.default_rng(role_seed(role))
    b = SPEC["input_bounds"]
    return [{"case_id": f"{prefix}-{i:04d}", **{k: float(np.round(rng.uniform(lo, hi), 4)) for k, (lo, hi) in b.items()}}
            for i in range(n)]


def pilot_plan(n_cases=12, n_cycles=40, n_refine=4, timeout_s=1500) -> dict:
    cases = lhs_cases(n_cases, "pilot", "pilot")
    # Refinement comparisons on deliberately different corners: coldest, warmest,
    # fastest first stage, and highest initial state of charge.
    pick = []
    for key, fn in (("t_amb_c", min), ("t_amb_c", max), ("c1", max), ("soc0", max)):
        c = fn(cases, key=lambda c: c[key])
        if c["case_id"] not in pick:
            pick.append(c["case_id"])
    pick = pick[:n_refine]
    checkpoints = list(range(1, n_cycles + 1))  # every cycle, so any shorter horizon can be evaluated
    jobs = [{"case": c, "n_cycles": n_cycles, "checkpoints": checkpoints, "role": "pilot"} for c in cases]
    # Refinements first: they are the longest, so they start early and finish with the rest.
    jobs = [{"case": c, "n_cycles": n_cycles, "checkpoints": checkpoints, "role": "pilot", "refined": True}
            for c in cases if c["case_id"] in pick] + jobs
    return {"plan": "battery-pilot-v1", "campaign_root": CAMPAIGN_ROOT, "spec": SPEC, "timeout_s": timeout_s,
            "jobs": jobs, "refined_case_ids": pick}


if __name__ == "__main__":  # pragma: no cover
    import sys

    json.dump(pilot_plan(), open(sys.argv[1], "w"), indent=1)

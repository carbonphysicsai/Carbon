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


def photonic_lhs(n: int, role: str, prefix: str) -> list[dict]:
    from scripts.dev.exam_design.photonic_reference import SPEC as PSPEC

    rng = np.random.default_rng(role_seed(role))
    b = PSPEC["input_bounds"]
    cols = {k: lo + (rng.permutation(n) + rng.uniform(size=n)) / n * (hi - lo) for k, (lo, hi) in b.items()}
    return [{"case_id": f"{prefix}-{i:04d}", **{k: float(np.round(cols[k][i], 3)) for k in b}} for i in range(n)]


def pilot2_plan() -> dict:
    """Refinement rerun for battery (memory-fixed) beside the photonic feasibility pilot."""
    p1 = pilot_plan()
    by_id = {j["case"]["case_id"]: j["case"] for j in p1["jobs"]}
    refine = p1["refined_case_ids"]
    ck = [1, 5, 10, 15, 20, 25, 30, 35, 40]
    bj = [{"case": by_id[c], "n_cycles": 40, "checkpoints": ck, "role": "pilot", "refined": True} for c in refine]
    bj += [{"case": by_id[c], "n_cycles": 40, "checkpoints": ck, "role": "pilot"} for c in refine + ["pilot-0007"]]
    pc = photonic_lhs(12, "photonic-pilot", "ppilot")
    pick = []
    for key, fn in (("gap_nm", min), ("gap_nm", max), ("length_um", max), ("length_um", min)):
        c = fn(pc, key=lambda c: c[key])
        if c["case_id"] not in pick:
            pick.append(c["case_id"])
    first = [c for c in pc if c["case_id"] in pick]
    rest = [c for c in pc if c["case_id"] not in pick]
    pj = [{"case": c, "role": "pilot", "timeout_s": 1200} for c in first]
    pj += [{"case": c, "role": "pilot", "refined": True, "timeout_s": 2700} for c in first]
    pj += [{"case": c, "role": "pilot", "timeout_s": 1200} for c in rest]
    return {"plan": "pilot-2", "campaign_root": CAMPAIGN_ROOT, "children": [
        {"phase": "battery_refs", "overlay": "battery",
         "config": {"jobs": bj, "timeout_s": 2400, "max_workers": 4}},
        {"phase": "photonic_refs", "overlay": "photonic", "config": {"jobs": pj, "timeout_s": 1200}}],
        "battery_refined_case_ids": refine, "photonic_refined_case_ids": pick}


MAIN_HORIZON = 30
MAIN_CHECKPOINTS = [1, 10, 20, 30]
ROLE_COUNTS = {"train": 400, "practice": 200, "final": 200, "verify": 200}
SCREEN_BATCHES, SCREEN_BATCH_SIZE = 6, 200
TWIN_SLOTS = ((10, 0), (20, 1))  # position of a hidden duplicate -> position it duplicates (inside every nested prefix)


def screen_batches() -> list[list[dict]]:
    """Each batch: 200 slots in a random order; two slots duplicate earlier slots (hidden paired probes).

    Nested sizes 50/100/200 are prefixes, so both duplicates sit inside every prefix.
    """
    out = []
    for b in range(SCREEN_BATCHES):
        role = f"screen-B{b:02d}"
        uniq = uniform_cases(SCREEN_BATCH_SIZE - len(TWIN_SLOTS), role, role)
        slots = list(uniq)
        for pos, src in TWIN_SLOTS:
            slots.insert(pos, dict(slots[src], case_id=f"{role}-dup{src}", duplicate_of=slots[src]["case_id"]))
        out.append(slots)
    return out


def main_cases() -> dict[str, list[dict]]:
    roles = {r: uniform_cases(n, r, r) for r, n in ROLE_COUNTS.items()}
    for b, slots in enumerate(screen_batches()):
        roles[f"screen-B{b:02d}"] = slots
    return roles


def refs_plan_a(n_refine: int = 16) -> dict:
    roles = main_cases()
    jobs = []
    for r in ("train", "practice", "final", "verify"):
        jobs += [{"case": c, "n_cycles": MAIN_HORIZON, "checkpoints": MAIN_CHECKPOINTS, "role": r} for c in roles[r]]
    # Reference-uncertainty sample: the first n TRAIN cases (a uniform draw), refined.
    refine = [{"case": c, "n_cycles": MAIN_HORIZON, "checkpoints": MAIN_CHECKPOINTS, "role": "train", "refined": True}
              for c in roles["train"][:n_refine]]
    return {"plan": "battery-refs-a", "campaign_root": CAMPAIGN_ROOT, "horizon": MAIN_HORIZON,
            "checkpoints": MAIN_CHECKPOINTS, "timeout_s": 1800, "max_workers": 7, "jobs": refine + jobs}


def refs_plan_b() -> dict:
    roles = main_cases()
    jobs = []
    for b in range(SCREEN_BATCHES):
        r = f"screen-B{b:02d}"
        jobs += [{"case": {k: v for k, v in c.items() if k != "duplicate_of"}, "n_cycles": MAIN_HORIZON,
                  "checkpoints": MAIN_CHECKPOINTS, "role": r, "batch": b} for c in roles[r] if "duplicate_of" not in c]
    return {"plan": "battery-refs-b", "campaign_root": CAMPAIGN_ROOT, "horizon": MAIN_HORIZON,
            "checkpoints": MAIN_CHECKPOINTS, "timeout_s": 1800, "max_workers": 6, "jobs": jobs}


def inputs_manifest() -> dict:
    """Every case's inputs, by role, with no reference outputs: what prediction workers receive."""
    cases = []
    for r, cs in main_cases().items():
        for c in cs:
            cases.append({"case_id": c["case_id"], "role": r, **{k: c[k] for k in ("c1", "c2", "t_amb_c", "soc0")}})
    return {"schema": "carbon.exam-design.inputs.v1", "campaign_root": CAMPAIGN_ROOT, "cases": cases}

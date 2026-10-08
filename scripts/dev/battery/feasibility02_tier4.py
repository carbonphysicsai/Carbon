"""Battery v3 boundary coverage (registry battery-feasibility-02/tier4-boundary-registry.json).

    python scripts/dev/battery/feasibility02_tier4.py plan-a RUNS OUT.json
    python scripts/dev/battery/feasibility02_tier4.py plan-b RUNS OUT.json
    python scripts/dev/battery/feasibility02_tier4.py plan-refine RUNS OUT.json
    python scripts/dev/battery/feasibility02_tier4.py score RUNS OUT.json

Test Lead 2026-10-08 (#846): the 5 C and 40 C bands of the ambient-indexed
v3 decision have three feasible actions each, too few for the contested
rule (>= 5 FEASIBLE and >= 5 near-limit INFEASIBLE per band). Stage A adds
a registered grid near both boundaries; stage B interpolates each observed
crossing of the binding limit and adds actions just either side of it;
cases within a band get the registered refined re-solve; the score counts
per band. Packet-v2 hard limits and bands are unchanged (verdicts from
feasibility02_v2).
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import feasibility02_v2 as v2

SOC0, SWITCH = 0.10, 4.0
DIRS = (
    "bfeas",
    "bfeas-t2",
    "bfeas-t2r",
    "bfeas-t3",
    "bfeas-t3r",
    "bfeas-t4a",
    "bfeas-t4b",
    "bfeas-t4r",
)
T_BAND, P_BAND = v2.T_BAND_C, v2.PLATING_BAND_V
#: stage-B targets: overshoots inside (1, 2] bands (near-limit INFEASIBLE)
#: and margins of 1.5 and 3 bands (FEASIBLE side)
PLATING_TARGETS_V = (-1.5 * P_BAND, -2.0 * P_BAND, 1.5 * P_BAND, 3.0 * P_BAND)
TEMP_TARGETS_C = (
    45.0 + 1.5 * T_BAND,
    45.0 + 2.0 * T_BAND,
    45.0 - 1.5 * T_BAND,
    45.0 - 3.0 * T_BAND,
)


def job(c1, c2, h, t, refined=False):
    cid = f"t4:c1={c1:g},c2={c2:g},sv={SWITCH:g}:h{h:g}:T{t:g}"
    return {"case_id": ("refined:" if refined else "") + cid, "c1": c1, "c2": c2, "t_amb_c": t, "soc0": SOC0,
            "h_multiplier": h, "switch_voltage_v": SWITCH, "refined": refined}  # fmt: skip


def key(c1, c2, h, t):
    return (round(c1, 4), round(c2, 4), round(h, 4), float(t))


def solved(runs):
    """{(c1, c2, h, T): (measures, refined measures or None)} over every tier."""
    rows = []
    for name in DIRS:
        path = Path(runs) / name / "records.jsonl"
        if path.exists():
            rows += [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    base, refined = {}, {}
    for r in rows:
        if r["status"] != "OK" or r["case_id"].startswith("control-"):
            continue
        if r.get("switch_voltage_v", SWITCH) != SWITCH or r.get("soc0", SOC0) != SOC0:
            continue
        k = key(r["c1"], r["c2"], r["h_multiplier"], r["t_amb_c"])
        (refined if r["case_id"].startswith("refined:") else base)[k] = v2.measures(r)
    return {k: (m, refined.get(k)) for k, m in base.items()}


def plan_a(runs):
    have = solved(runs)
    jobs = []
    for c1 in (0.25, 0.5, 0.75, 1.0, 1.125, 1.375):
        for c2 in (0.25, 0.4, 0.5, 0.6):
            if c2 <= c1:
                jobs.append(job(c1, c2, 1.0, 5.0))
    slow = [(c1, c2) for c1 in (0.5, 0.75, 1.0) for c2 in (0.4, 0.7, 1.0) if c2 <= c1]
    jobs += [job(c1, c2, h, 40.0) for c1, c2 in slow for h in (1.0, 2.0, 4.0)]
    jobs += [
        job(c1, c2, h, 40.0)
        for c1 in (1.25, 1.5)
        for c2 in (0.4, 0.7, 1.0)
        for h in (3.0, 6.0)
    ]
    return jobs


def _cross(points, targets, step, lo, hi, transform=lambda x: x):
    """Linear interpolation (in transform(x)) of each sign change of
    value - target between neighbouring points; rounded to `step`."""
    out = set()
    pts = sorted(points)
    for target in targets:
        for (x0, y0), (x1, y1) in itertools.pairwise(pts):
            if (y0 - target) * (y1 - target) < 0:
                u0, u1 = transform(x0), transform(x1)
                u = u0 + (target - y0) * (u1 - u0) / (y1 - y0)
                x = round(round(_inverse(transform, u, x0, x1) / step) * step, 6)
                if lo <= x <= hi:
                    out.add(x)
    return out


def _inverse(transform, u, x0, x1):
    for _ in range(60):  # bisection; transforms are monotone
        mid = (x0 + x1) / 2
        if (transform(mid) - u) * (transform(x0) - u) > 0:
            x0 = mid
        else:
            x1 = mid
    return (x0 + x1) / 2


def plan_b(runs):
    have = solved(runs)
    new = set()
    # 5 C: plating binds. Rows at fixed c1 along c2, and at fixed c2 along c1.
    cold = {k: m for k, (m, _) in have.items() if k[3] == 5.0 and k[2] == 1.0}
    for c1 in {k[0] for k in cold}:
        pts = [(k[1], m["plating_min_v"]) for k, m in cold.items() if k[0] == c1]
        new |= {
            (c1, c2, 1.0, 5.0) for c2 in _cross(pts, PLATING_TARGETS_V, 0.01, 0.2, c1)
        }
    for c2 in {k[1] for k in cold}:
        pts = [(k[0], m["plating_min_v"]) for k, m in cold.items() if k[1] == c2]
        new |= {
            (c1, c2, 1.0, 5.0) for c1 in _cross(pts, PLATING_TARGETS_V, 0.01, c2, 2.0)
        }
    # 40 C: charging temperature binds. Rows along the cooling level (in 1/h)
    # and along c1 at fixed (c2, h).
    warm = {k: m for k, (m, _) in have.items() if k[3] == 40.0}
    for c1, c2 in {(k[0], k[1]) for k in warm}:
        pts = [
            (k[2], m["charging_t_max_c"])
            for k, m in warm.items()
            if (k[0], k[1]) == (c1, c2)
        ]
        hs = _cross(pts, TEMP_TARGETS_C, 0.1, 1.0, 8.0, transform=lambda h: 1.0 / h)
        new |= {(c1, c2, h, 40.0) for h in hs}
    for c2, h in {(k[1], k[2]) for k in warm}:
        pts = [
            (k[0], m["charging_t_max_c"])
            for k, m in warm.items()
            if (k[1], k[2]) == (c2, h)
        ]
        new |= {(c1, c2, h, 40.0) for c1 in _cross(pts, TEMP_TARGETS_C, 0.01, c2, 2.0)}
    return [job(*k) for k in sorted(new) if key(*k) not in have and k[1] <= k[0]]


def plan_refine(runs):
    jobs = []
    for k, (m, ref) in solved(runs).items():
        if ref is not None or k[3] not in (5.0, 40.0):
            continue
        near_t = abs(45.0 - m["charging_t_max_c"]) <= T_BAND
        near_p = abs(m["plating_min_v"]) <= P_BAND
        if near_t or near_p:
            jobs.append(job(*k, refined=True))
    return jobs


def score(runs):
    have = solved(runs)
    out = {}
    for t in (5.0, 40.0):
        rows = []
        for k, (m, ref) in have.items():
            if k[3] != t:
                continue
            outcome, why = v2.verdict(m, ref)
            over_t = (m["charging_t_max_c"] - 45.0) / T_BAND
            over_p = -m["plating_min_v"] / P_BAND
            rows.append({"action": f"c1={k[0]:g},c2={k[1]:g},h{k[2]:g}", "outcome": outcome, "why": why,
                         "overshoot_bands": max(over_t, over_p), "minutes": m["minutes"],
                         "charging_t_max_c": m["charging_t_max_c"], "plating_min_v": m["plating_min_v"],
                         "q30_over_q1": m["q30_over_q1"]})  # fmt: skip
        feas = [r for r in rows if r["outcome"] == "FEASIBLE"]
        infeas = [r for r in rows if r["outcome"] == "INFEASIBLE"]
        near2 = [
            r
            for r in infeas
            if r["overshoot_bands"] <= 2.0
            and set(r["why"]) <= {"plating", "charging_temperature"}
        ]
        near5 = [
            r
            for r in infeas
            if r["overshoot_bands"] <= 5.0
            and set(r["why"]) <= {"plating", "charging_temperature"}
        ]
        unres = [r for r in rows if r["outcome"] == "REFERENCE_UNRESOLVED"]
        out[f"T{t:g}"] = {
            "actions": len(rows), "feasible": len(feas), "infeasible": len(infeas),
            "infeasible_within_2_bands": len(near2), "infeasible_within_5_bands": len(near5),
            "unresolved": len(unres), "unresolved_rate": len(unres) / len(rows) if rows else None,
            "contested_2_bands": len(feas) >= 5 and len(near2) >= 5,
            "contested_5_bands": len(feas) >= 5 and len(near5) >= 5,
            "pass_fraction_reported": len(feas) / (len(feas) + len(infeas)) if feas or infeas else None,
            "best": min(feas, key=lambda r: r["minutes"]) if feas else None,
            "rows": sorted(rows, key=lambda r: r["action"]),
        }  # fmt: skip
    return out


def main(cmd, runs, out):
    if cmd == "score":
        doc = {"schema": "carbon.battery.tier4-boundary.v1", "bands": score(runs)}
        Path(out).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
        for b, v in doc["bands"].items():
            print(b, {k: v[k] for k in ("actions", "feasible", "infeasible", "infeasible_within_2_bands",
                                        "infeasible_within_5_bands", "unresolved")})  # fmt: skip
        return
    jobs = {
        "plan-a": lambda: plan_a(runs),
        "plan-b": lambda: plan_b(runs),
        "plan-refine": lambda: plan_refine(runs),
    }[cmd]()
    Path(out).write_text(
        json.dumps(
            {
                "batch": f"battery-feas02-tier4-{cmd}",
                "pr": "#846 (diagnostic)",
                "jobs": jobs,
            },
            indent=1,
        )
        + "\n"
    )
    print(len(jobs))


if __name__ == "__main__":
    main(*sys.argv[1:4])

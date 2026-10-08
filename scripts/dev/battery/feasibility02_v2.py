"""Battery feasibility re-scored under packet v2 (#804), per the registry
battery-feasibility-02/v2-rescore-registry.json. Existing records only.

    python scripts/dev/battery/feasibility02_v2.py RUNS_DIR OUT.json
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

T_BAND_C, PLATING_BAND_V, TIME_TIE_MIN = 0.5, 0.002, 0.5
CHARGE = ("cc1", "cc2", "cv")
AMBIENTS = (5.0, 15.0, 25.0, 35.0, 40.0)


def action_id(r):
    cid = r["case_id"]
    if cid.startswith("t2:"):
        return cid[3:].rsplit(":T", 1)[0]
    return f"{cid.rsplit(':T', 1)[0].replace(':h', ',sv=4:h')}"


def measures(r):
    charging = max(
        p[n]["t_max_c"]
        for c in r["per_cycle"]
        for n, p in [(k, c["phases"]) for k in CHARGE]
    )
    plating = min(
        c["phases"][n]["plating_min_v"] for c in r["per_cycle"] for n in CHARGE
    )
    rests = {
        "initial_rest_max_c": r["initial_rest"]["t_max_c"],
        "rest_after_charge_max_c": max(
            c["phases"]["rest_after_charge"]["t_max_c"] for c in r["per_cycle"]
        ),
        "discharge_max_c": max(
            c["phases"]["discharge"]["t_max_c"] for c in r["per_cycle"]
        ),
        "rest_after_discharge_max_c": max(
            c["phases"]["rest_after_discharge"]["t_max_c"] for c in r["per_cycle"]
        ),
    }
    clock = r["soc_clock"]
    return {
        "charging_t_max_c": charging,
        "plating_min_v": plating,
        "v_max_v": r["whole_programme"]["v_max_v"],
        "q30_over_q1": r["q30_over_q1"],
        "minutes": clock.get("minutes") if clock["status"] == "REACHED" else None,
        "whole_programme_t_max_c": r["whole_programme"]["t_max_c"],
        **rests,
    }


def verdict(m, refined=None):
    fails, band = [], []
    t_margin = 45.0 - m["charging_t_max_c"]
    if t_margin < -T_BAND_C:
        fails.append("charging_temperature")
    elif abs(t_margin) <= T_BAND_C:
        band.append("charging_temperature")
    if m["plating_min_v"] < -PLATING_BAND_V:
        fails.append("plating")
    elif abs(m["plating_min_v"]) <= PLATING_BAND_V:
        band.append("plating")
    if m["v_max_v"] > 4.2 + 1e-6:
        fails.append("voltage")
    if m["q30_over_q1"] < 0.99:
        fails.append("retention")
    if refined is not None:
        keep = []
        for name in band:
            key, limit, width = {
                "charging_temperature": ("charging_t_max_c", 45.0, T_BAND_C),
                "plating": ("plating_min_v", 0.0, PLATING_BAND_V),
            }[name]
            a, b = m[key], refined[key]
            change = abs(a - b)
            sign = 1 if name == "plating" else -1  # plating passes above, T below
            settled = change < width and all(
                sign * (x - limit) - change > 0 for x in (a, b)
            )
            if not settled:
                keep.append(name)
        band = keep
    if fails:
        return "INFEASIBLE", fails
    if band:
        return "REFERENCE_UNRESOLVED", band
    if m["minutes"] is None:
        return "REFERENCE_UNRESOLVED", ["objective_not_reached"]
    return "FEASIBLE", []


def main(runs, out):
    runs = Path(runs)
    rows = []
    for name in ("bfeas", "bfeas-t2", "bfeas-t2r"):
        rows += [
            json.loads(x)
            for x in (runs / name / "records.jsonl").read_text().splitlines()
            if x.strip()
        ]
    refined = {}
    for r in rows:
        if r["case_id"].startswith("refined:") and r["status"] == "OK":
            refined[r["case_id"].split("refined:", 1)[1]] = measures(r)
    cells, per_stratum = {}, {}
    for r in rows:
        cid = r["case_id"]
        if cid.startswith(("refined:", "control-")) or r["status"] != "OK":
            continue
        m = measures(r)
        outcome, why = verdict(m, refined.get(cid))
        act, t = action_id(r), r["t_amb_c"]
        cells[(act, t)] = {"outcome": outcome, "why": why, **m}
    for t in AMBIENTS:
        mine = {a: c for (a, tt), c in cells.items() if tt == t}
        feas = {a: c for a, c in mine.items() if c["outcome"] == "FEASIBLE"}
        best = min(feas.items(), key=lambda kv: kv[1]["minutes"]) if feas else None
        per_stratum[f"T{t:g}"] = {
            "actions": len(mine),
            "counts": dict(collections.Counter(c["outcome"] for c in mine.values())),
            "infeasible_reasons": dict(
                collections.Counter(
                    w
                    for c in mine.values()
                    if c["outcome"] == "INFEASIBLE"
                    for w in c["why"]
                )
            ),
            "feasible_set": sorted(feas),
            "best_feasible": (
                None
                if best is None
                else {"action": best[0], "minutes": best[1]["minutes"]}
            ),
            "best_feasible_protocol_only": min(
                ((a, c["minutes"]) for a, c in feas.items() if a.endswith(":h1")),
                key=lambda x: x[1],
                default=None,
            ),
            "discharge_diagnostics": {
                "discharge_max_c_range": [
                    min(c["discharge_max_c"] for c in mine.values()),
                    max(c["discharge_max_c"] for c in mine.values()),
                ],
                "actions_with_discharge_above_45c": sum(
                    c["discharge_max_c"] > 45.0 for c in mine.values()
                ),
                "rest_after_discharge_max_c_range": [
                    min(c["rest_after_discharge_max_c"] for c in mine.values()),
                    max(c["rest_after_discharge_max_c"] for c in mine.values()),
                ],
            },
        }
    actions = sorted({a for a, _ in cells})
    decision = {}
    for a in actions:
        states = {
            t: cells.get((a, t), {"outcome": "COVERAGE_MISSING"})["outcome"]
            for t in AMBIENTS
        }
        if all(s == "FEASIBLE" for s in states.values()):
            status = "ADMISSIBLE"
        elif any(s == "INFEASIBLE" for s in states.values()):
            status = "INADMISSIBLE"
        else:
            status = "UNRESOLVED"
        warm = [
            cells[(a, t)]["minutes"]
            for t in (25.0, 35.0)
            if (a, t) in cells and cells[(a, t)]["minutes"] is not None
        ]
        decision[a] = {
            "status": status,
            "per_ambient": states,
            "worst_25_35_minutes": max(warm) if len(warm) == 2 else None,
        }
    admissible = {a: d for a, d in decision.items() if d["status"] == "ADMISSIBLE"}
    unresolved = {a: d for a, d in decision.items() if d["status"] == "UNRESOLVED"}

    def pick(pool):
        if not pool:
            return None
        a, d = min(pool.items(), key=lambda kv: kv[1]["worst_25_35_minutes"])
        rivals = [
            b for b, e in {**admissible, **unresolved}.items()
            if b != a and e["worst_25_35_minutes"] is not None and e["worst_25_35_minutes"] - d["worst_25_35_minutes"] <= TIME_TIE_MIN
            and (b in pool or e["status"] == "UNRESOLVED")
        ]  # fmt: skip
        return {"action": a, "worst_25_35_minutes": d["worst_25_35_minutes"],
                "resolved": not rivals, "within_0.5_min": rivals}  # fmt: skip

    document = {
        "schema": "carbon.battery.feasibility02-v2-rescore.v1",
        "packet": "battery v2, #804 @ fed63497",
        "per_stratum": per_stratum,
        "decision": {
            "actions": len(decision),
            "counts": dict(collections.Counter(d["status"] for d in decision.values())),
            "admissible": sorted(admissible),
            "pick_all_actions": pick(admissible),
            "pick_protocol_only": pick({a: d for a, d in admissible.items() if a.endswith(":h1")}),
            "unresolved_by_reason": dict(collections.Counter(
                "coverage_missing" if "COVERAGE_MISSING" in d["per_ambient"].values() else "reference_unresolved"
                for d in unresolved.values())),  # fmt: skip
        },
        "actions": decision,
        "cells": {f"{a}@T{t:g}": c for (a, t), c in sorted(cells.items())},
    }
    Path(out).write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    return document


if __name__ == "__main__":
    doc = main(sys.argv[1], sys.argv[2])
    print(
        json.dumps(
            {
                "per_stratum": {
                    k: {
                        x: v[x]
                        for x in (
                            "counts",
                            "best_feasible",
                            "best_feasible_protocol_only",
                            "infeasible_reasons",
                            "discharge_diagnostics",
                        )
                    }
                    for k, v in doc["per_stratum"].items()
                },
                "decision": doc["decision"],
            },
            indent=1,
        )
    )

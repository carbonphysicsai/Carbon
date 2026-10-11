"""Battery feasibility (#758 at 1ac5acfa): outcome counts by stratum from the
tier-1, tier-2 and refined records (registry bands: 1 min, 0.5 C, 2 mV)."""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

BANDS = {"time_min": 1.0, "t_c": 0.5, "plating_v": 0.002}


def metrics(r):
    w, s = r["whole_programme"], r["soc_clock"]
    return {
        "minutes": s["minutes"] if s["status"] == "REACHED" else None,
        "t_max_c": w["t_max_c"],
        "t_max_charging_c": w["t_max_charging_c"],
        "t_max_non_charging_c": w["t_max_non_charging_c"],
        "plating_min_v": w["plating_min_v"],
        "v_max_v": w["v_max_v"],
        "q30_over_q1": r["q30_over_q1"],
    }


def verdict(m, speed, refined=None):
    """FEASIBLE, INFEASIBLE(reasons) or UNRESOLVED(reasons)."""
    fails, band = [], []

    def check(name, margin, width):
        if margin < -width:
            fails.append(name)
        elif abs(margin) <= width:
            band.append(name)

    if speed:
        if m["minutes"] is None:
            fails.append("charge_time_not_reached")
        else:
            check("charge_time", 30.0 - m["minutes"], BANDS["time_min"])
    check("thermal_charging", 45.0 - m["t_max_charging_c"], BANDS["t_c"])
    check("thermal_non_charging", 45.0 - m["t_max_non_charging_c"], BANDS["t_c"])
    check("plating", m["plating_min_v"], BANDS["plating_v"])
    if m["v_max_v"] > 4.2 + 1e-6:
        fails.append("voltage")
    if m["q30_over_q1"] < 0.99:
        fails.append("retention")
    if refined is not None:
        # A rung change no larger than the packet's demand and no sign change
        # resolves the band; a straddle or an interval touching the limit stays
        # unresolved.
        resolved = []
        for name in band:
            if name == "plating":
                lo = min(m["plating_min_v"], refined["plating_min_v"])
                change = abs(m["plating_min_v"] - refined["plating_min_v"])
                if lo - change > 0:
                    resolved.append(name)
            elif name == "charge_time" and refined["minutes"] is not None:
                change = abs(m["minutes"] - refined["minutes"]) * 60
                if (
                    change <= 30
                    and max(m["minutes"], refined["minutes"]) + change / 60 < 30
                ):
                    resolved.append(name)
        band = [b for b in band if b not in resolved]
    if fails:
        return "RESOLVED_INFEASIBLE", fails
    if band:
        return "REFERENCE_UNRESOLVED", band
    return "RESOLVED_FEASIBLE", []


def main(runs):
    runs = Path(runs)
    rows = []
    for name in ("bfeas", "bfeas-t2", "bfeas-t2r"):
        path = runs / name / "records.jsonl"
        rows += [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    refined = {
        r["case_id"].split("refined:", 1)[1].replace("c1=2,c2=1:", "c1=2,c2=1:"): r
        for r in rows
        if r["case_id"].startswith("refined:")
    }
    out = {"counts": {}, "reasons": {}, "cases": []}
    for r in rows:
        cid = r["case_id"]
        if cid.startswith(("refined:", "control-")):
            continue
        t = r["t_amb_c"]
        speed = t in (25.0, 35.0)
        if r["status"] != "OK":
            outcome, why = (
                (
                    "FAILED_INFRA"
                    if r["status"] == "FAILED_INFRA"
                    else "REFERENCE_UNRESOLVED"
                ),
                [r["status"]],
            )
        else:
            ref = refined.get(cid)
            outcome, why = verdict(
                metrics(r),
                speed,
                metrics(ref) if ref and ref["status"] == "OK" else None,
            )
        stratum = f"T{t:g}"
        out["counts"].setdefault(stratum, collections.Counter())[outcome] += 1
        for w in why:
            out["reasons"].setdefault(stratum, collections.Counter())[w] += 1
        out["cases"].append(
            {"case_id": cid, "stratum": stratum, "outcome": outcome, "why": why,
             **(metrics(r) if r["status"] == "OK" else {})}
        )  # fmt: skip
    out["controls"] = [
        {"case_id": r["case_id"], "minutes_to_80": r["soc_clock"].get("minutes"),
         "soc10_time_s": r["soc_clock"].get("soc10_time_s"),
         "t_max_c": r["whole_programme"]["t_max_c"]}
        for r in rows if r["case_id"].startswith("control-")
    ]  # fmt: skip
    out["refined"] = [
        {"case_id": r["case_id"], **metrics(r)}
        for r in rows
        if r["case_id"].startswith("refined:")
    ]
    return out


if __name__ == "__main__":
    document = main(sys.argv[1])
    Path(sys.argv[2]).write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(
        json.dumps(
            {"counts": document["counts"], "reasons": document["reasons"]}, indent=1
        )
    )

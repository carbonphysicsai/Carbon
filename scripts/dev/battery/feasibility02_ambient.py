"""Battery feasibility: the ambient-indexed DIAGNOSTIC decision (registry
battery-feasibility-02/tier3-ambient-indexed-registry.json). One protocol
per ambient band, each meeting packet-v2's hard limits at its own ambient.
A proposed buyer revision the owner has not adopted.

    python scripts/dev/battery/feasibility02_ambient.py RUNS_DIR OUT.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import feasibility02_v2 as v2

AMBIENTS = (5.0, 15.0, 25.0, 35.0, 40.0)
TIE_MIN = 0.5


def action_id(case_id):
    cid = case_id.split(":", 1)[1] if case_id.startswith(("t2:", "t3:")) else case_id
    act = cid.rsplit(":T", 1)[0]
    return act if ",sv=" in act else act.replace(":h", ",sv=4:h")


def cells(runs):
    rows = []
    for name in ("bfeas", "bfeas-t2", "bfeas-t2r", "bfeas-t3", "bfeas-t3r"):
        path = Path(runs) / name / "records.jsonl"
        rows += [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    refined = {
        r["case_id"].split("refined:", 1)[1]: v2.measures(r)
        for r in rows
        if r["case_id"].startswith("refined:") and r["status"] == "OK"
    }
    out = {}
    for r in rows:
        cid = r["case_id"]
        if cid.startswith(("refined:", "control-")) or r["status"] != "OK":
            continue
        m = v2.measures(r)
        outcome, why = v2.verdict(m, refined.get(cid))
        out[(action_id(cid), r["t_amb_c"])] = {"outcome": outcome, "why": why, **m}
    return out


def band(cs, t, protocol_only):
    mine = {
        a: c
        for (a, tt), c in cs.items()
        if tt == t and (not protocol_only or a.endswith(":h1"))
    }
    feas = {a: c for a, c in mine.items() if c["outcome"] == "FEASIBLE"}
    unres = {a: c for a, c in mine.items() if c["outcome"] == "REFERENCE_UNRESOLVED"}
    best = min(feas.items(), key=lambda kv: kv[1]["minutes"]) if feas else None
    rivals = []
    if best:
        rivals = [
            a
            for a, c in {**feas, **unres}.items()
            if a != best[0]
            and c["minutes"] is not None
            and c["minutes"] - best[1]["minutes"] <= TIE_MIN
        ]
    return {
        "actions": len(mine),
        "feasible": sorted(feas),
        "unresolved": sorted(unres),
        "unresolved_count": len(unres),
        "best": None if best is None else {"action": best[0], "minutes": best[1]["minutes"],
                                           "charging_t_max_c": best[1]["charging_t_max_c"],
                                           "plating_min_v": best[1]["plating_min_v"]},
        "pick_resolved": None if best is None else not rivals,
        "rivals_within_0.5_min": rivals,
    }  # fmt: skip


def main(runs, out):
    cs = cells(runs)
    lanes = {}
    for lane, protocol_only in (("protocol_only", True), ("with_cooling", False)):
        bands = {f"T{t:g}": band(cs, t, protocol_only) for t in AMBIENTS}
        complete = all(b["feasible"] for b in bands.values())
        warm = [bands[k]["best"]["minutes"] for k in ("T25", "T35") if bands[k]["best"]]
        lanes[lane] = {
            "bands": bands,
            "complete_feasible_map": complete,
            "objective_worst_25_35_minutes": max(warm) if len(warm) == 2 else None,
            "map": {
                k: (b["best"]["action"] if b["best"] else None)
                for k, b in bands.items()
            },
        }
    document = {
        "schema": "carbon.battery.feasibility02-ambient-indexed.v1",
        "status": "DIAGNOSTIC: a proposed ambient-indexed buyer revision, not adopted",
        "packet_rules": "battery v2 hard limits (#804 @ fed63497)",
        "lanes": lanes,
    }
    Path(out).write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    return document


if __name__ == "__main__":
    doc = main(sys.argv[1], sys.argv[2])
    for lane, v in doc["lanes"].items():
        print(
            lane,
            "complete map:",
            v["complete_feasible_map"],
            "objective:",
            v["objective_worst_25_35_minutes"],
        )
        for k, b in v["bands"].items():
            print("  ", k, len(b["feasible"]), "feasible,", b["unresolved_count"], "unresolved; best",
                  b["best"] and (b["best"]["action"], round(b["best"]["minutes"], 1)), "resolved", b["pick_resolved"])  # fmt: skip

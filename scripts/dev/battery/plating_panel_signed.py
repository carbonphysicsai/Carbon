"""D2 per-case signed differences and aggregates from a panel run's records."""

import json
import sys
from pathlib import Path

out_dir, cases_path = Path(sys.argv[1]), Path(sys.argv[2])
cases = json.loads(cases_path.read_text())["cases"]
records = [
    json.loads(x)
    for x in (out_dir / "files/study/records.jsonl").read_text().splitlines()
    if x
]
by = {}
for r in records:
    by.setdefault(r["case"], {})[r["mesh"]] = r
rows = []
for i, c in enumerate(cases):
    m = {
        k: v.get("plating_margin_v")
        for k, v in by.get(i, {}).items()
        if v.get("status") == "OK"
    }
    row = {
        "case_id": c["case_id"], "tier": c.get("panel_tier", c.get("stratum")),
        "status": c.get("reference_status"), "t_amb_c": c["t_amb_c"], "soc0": c["soc0"],
        "c1": c["c1"], "c2": c["c2"],
        "mesh20_mv": None if 20 not in m else m[20] * 1e3,
        "mesh40_mv": None if 40 not in m else m[40] * 1e3,
        "mesh80_mv": None if 80 not in m else m[80] * 1e3,
        "mesh160_mv": None if 160 not in m else m[160] * 1e3,
        "d20_160_mv": None if 20 not in m or 160 not in m else (m[20] - m[160]) * 1e3,
        "d80_160_mv": None if 80 not in m or 160 not in m else (m[80] - m[160]) * 1e3,
        "d40_160_mv": None if 40 not in m or 160 not in m else (m[40] - m[160]) * 1e3,
        "failed": sorted(k for k, v in by.get(i, {}).items() if v.get("status") != "OK"),
    }  # fmt: skip
    rows.append(row)
d20 = [r["d20_160_mv"] for r in rows if r["d20_160_mv"] is not None]
d80 = [r["d80_160_mv"] for r in rows if r["d80_160_mv"] is not None]
neg = [r for r in rows if (r["d20_160_mv"] or 0) < 0 or (r["d80_160_mv"] or 0) < 0]
pos_feas = [
    r
    for r in rows
    if r["status"] == "FEASIBLE" and r["mesh20_mv"] is not None and r["mesh20_mv"] > 0
]
summary = {
    "cases": len(rows),
    "complete": len(d20),
    "failed_rungs": sum(len(r["failed"]) for r in rows),
    "d20_160_mv": {"min": min(d20), "max": max(d20)} if d20 else None,
    "d80_160_mv": {"min": min(d80), "max": max(d80)} if d80 else None,
    "negative_differences": [(r["case_id"], r["d20_160_mv"], r["d80_160_mv"]) for r in neg],
    "positive_feasible_worst_d20_160_mv": max((r["d20_160_mv"] for r in pos_feas if r["d20_160_mv"] is not None), default=None),
    "positive_feasible_max_d80_160_mv": max((r["d80_160_mv"] for r in pos_feas if r["d80_160_mv"] is not None), default=None),
    "positive_feasible_now_plating_at_160": [r["case_id"] for r in pos_feas if r["mesh160_mv"] is not None and r["mesh160_mv"] < 0],
}  # fmt: skip
(out_dir / "d2-signed.json").write_text(
    json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n"
)
print(json.dumps(summary, indent=1))
for r in rows:
    print(r["tier"], r["case_id"], r["t_amb_c"], r["soc0"], r["c1"], r["c2"],
          *(None if r[k] is None else round(r[k], 3) for k in ("mesh20_mv", "mesh40_mv", "mesh80_mv", "mesh160_mv", "d20_160_mv", "d40_160_mv", "d80_160_mv")))  # fmt: skip

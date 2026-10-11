"""#965 battery v3 middle-band panel: manifest, exact reuse check, stage-A plan.

    python scripts/dev/battery/middle_bands.py manifest SHEET.json RUNS OUT_DIR

BATTERY-V3-MIDDLE-BANDS-PANEL-01 (main, merged #965): expand the sheet's
groups (inclusive 0.01-C ranges, fixed lists, c2 <= c1), sort, hash; join every
tuple against completed standard, rung-2 and rung-3 records by the complete
physical identity (truth overlay/model, SOC0 0.10, switch 4.00 V, cooling
multiplier, ambient, c1, c2 at two decimals) and rung. A reused result keeps
its original record identity; only tuples without a standard record get a new
standard solve. Rung-2/3 follow the panel's refinement rule after the
standard results exist.
"""

from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import feasibility02_tier4 as t4

RUNG_DIRS = {"standard_and_rung2": t4.DIRS, "rung3": ("bfeas-t6r3",)}
STEP = Decimal("0.01")


def _range(lo, hi):
    a, b = Decimal(lo), Decimal(hi)
    out = []
    while a <= b:
        out.append(a)
        a += STEP
    return out


def expand(sheet):
    rows = []
    for g in sheet["groups"]:
        c1s = (
            [Decimal(x) for x in g["c1_list"]]
            if "c1_list" in g
            else _range(*g["c1_range"])
        )
        c2s = (
            [Decimal(x) for x in g["c2_list"]]
            if "c2_list" in g
            else _range(*g["c2_range"])
        )
        group = [(c1, c2) for c1 in c1s for c2 in c2s if c2 <= c1]
        if len(group) != g["rows"]:
            raise SystemExit(f"{g['id']}: {len(group)} tuples, sheet says {g['rows']}")
        for c1, c2 in group:
            rows.append({"id": f"bmid1:T{g['ambient_c']}:h{g['cooling']}:c1={c1:.2f}:c2={c2:.2f}:sv=4.00:SOC=.10",
                         "group": g["id"], "ambient_c": g["ambient_c"], "cooling": g["cooling"],
                         "c1": f"{c1:.2f}", "c2": f"{c2:.2f}"})  # fmt: skip
    rows.sort(
        key=lambda r: (r["ambient_c"], r["group"], Decimal(r["c1"]), Decimal(r["c2"]))
    )
    return rows


def _key(c1, c2, h, t, sv=4.0):
    return (
        f"{Decimal(str(c1)):.2f}",
        f"{Decimal(str(c2)):.2f}",
        f"{float(sv):.2f}",
        float(h),
        float(t),
    )


def solved(runs):
    """{key: {rung: case_id}} over every completed OK record at SOC0 0.10."""
    out = {}
    for rung_group, dirs in RUNG_DIRS.items():
        for name in dirs:
            path = Path(runs) / name / "records.jsonl"
            if not path.exists():
                continue
            for line in path.read_text().splitlines():
                r = json.loads(line) if line.strip() else None
                if (
                    not r
                    or r["status"] != "OK"
                    or r["case_id"].startswith("control-")
                    or r.get("soc0", 0.1) != 0.1
                ):
                    continue
                k = _key(
                    r["c1"],
                    r["c2"],
                    r["h_multiplier"],
                    r["t_amb_c"],
                    r.get("switch_voltage_v", 4.0),
                )
                if rung_group == "rung3":
                    rung = "rung3"
                else:
                    rung = (
                        "rung2" if r["case_id"].startswith("refined:") else "standard"
                    )
                out.setdefault(k, {}).setdefault(rung, r["case_id"])
    return out


def manifest(sheet_path, runs, out_dir):
    sheet = json.loads(Path(sheet_path).read_text())
    rows = expand(sheet)
    have = solved(runs)
    jobs, inventory = [], {"standard": 0, "rung2": 0, "rung3": 0}
    for row in rows:
        k = _key(row["c1"], row["c2"], row["cooling"], row["ambient_c"])
        found = have.get(k, {})
        row["reuse"] = found
        for rung in found:
            inventory[rung] += 1
        if "standard" not in found:
            jobs.append({"case_id": f"t7:{row['id']}", "c1": float(row["c1"]), "c2": float(row["c2"]),
                         "t_amb_c": float(row["ambient_c"]), "soc0": 0.1, "h_multiplier": float(row["cooling"]),
                         "switch_voltage_v": 4.0, "refined": False})  # fmt: skip
    body = {"schema": "carbon.battery.middle-bands-manifest.v1", "ticket": "BATTERY-V3-MIDDLE-BANDS-PANEL-01",
            "sheet_sha256": hashlib.sha256(Path(sheet_path).read_bytes()).hexdigest(), "tuples": rows}  # fmt: skip
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(
        json.dumps({**body, "manifest_sha256": digest}, indent=1) + "\n"
    )
    (out / "stage-a-plan.json").write_text(
        json.dumps(
            {"batch": "battery-v3-middle-bands-A", "pr": "#965", "jobs": jobs}, indent=1
        )
        + "\n"
    )
    by_band = {}
    for row in rows:
        b = by_band.setdefault(
            row["ambient_c"],
            {"tuples": 0, "standard_reused": 0, "rung2_reused": 0, "rung3_reused": 0},
        )
        b["tuples"] += 1
        for rung in row["reuse"]:
            b[f"{rung}_reused"] += 1
    summary = {
        "manifest_sha256": digest,
        "tuples": len(rows),
        "new_standard_jobs": len(jobs),
        "reused": inventory,
        "by_band": by_band,
    }
    (out / "reuse-inventory.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(manifest(*sys.argv[2:5]), indent=1))

"""Judge f17 bulk-run outputs where they ran (pod or local), against the bands
registered in F17-SCIENCE-VALUES-01 before the runs.

    python3 f17_pod_judge.py --cases BULK_OUT/cases/f17 --out OUT [--periodic C5.json]

CASES holds one ``<case>/work`` dir per frozen triage case. Writes compact
JSON only (no fields): ``observed/<case>.json``, ``judge.json``. A failing
check stays a finding; nothing here re-bands. DEVELOPMENT engineering
evidence, never qualification.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f17_extract as ex
import f17_proof as proof

FLOORS = (0.80, 0.85)
NEAR = 0.04  # F5/F8 two-band rule
WITNESSES = (("deep-dense-primary", "deep-dense-h7.071"),
             ("deep-sparse-primary", "deep-sparse-h7.071"))  # fmt: skip


def design_row(o):
    """Worst-condition answer inputs for one design (F3/F4)."""
    panel = {
        k: v
        for k, v in o["scalars"].items()
        if v.get("scheme") == o["scalars"].get("scalar_q5_d0.5", {}).get("scheme")
        and v.get("diffusivity_m2_s", 0) > 0
        and "mixing" in v
    }
    worst = min(panel.values(), key=lambda v: v["mixing"]) if panel else None
    flows = o["flows"].values()
    return {
        "design": o["design"],
        "conditions": len(panel),
        "all_converged": all(v.get("converged") for v in panel.values())
        and all(f.get("converged") for f in flows),
        "worst_M": worst["mixing"] if worst else None,
        "worst_condition": worst["dir"] if worst else None,
        "max_delta_p_pa": max((f["delta_p_pa"] for f in flows), default=None),
        "residence_q1_s": next(
            (v["residence_s"] for v in panel.values() if v["flow_ul_min"] == 1), None
        ),
        "volume_ok": o["mesh"]["volume_ok"],
        "near_floor": [f for f in FLOORS if worst and abs(worst["mixing"] - f) <= NEAR],
    }


def judge(cases_dir, out, periodic=None):
    cases_dir, out = Path(cases_dir), Path(out)
    (out / "observed").mkdir(parents=True, exist_ok=True)
    obs, errors = {}, {}
    for case in sorted(p for p in cases_dir.iterdir() if (p / "work").is_dir()):
        try:
            o = ex.observe(case / "work")
        except (OSError, ValueError, KeyError, IndexError, TypeError):  # a finding
            errors[case.name] = traceback.format_exc(limit=3)
            continue
        obs[case.name] = case / "work"
        (out / "observed" / f"{case.name}.json").write_text(
            json.dumps(o, indent=1, default=float) + "\n"
        )
    result = {"schema": "carbon.f17.pod-judge.v1", "decision": proof.DECISION,
              "observe_errors": errors}  # fmt: skip
    # D1 two-mesh and D2 high-Pe on both witnesses (refined rung)
    result["witnesses"] = {}
    for prim, ref in WITNESSES:
        if prim in obs and ref in obs:
            result["witnesses"][ref] = proof.convergence(obs[prim], obs[ref])
        else:
            result["witnesses"][ref] = {"state": "MISSING", "have": sorted(obs)}
    # triage panel: per-design answer inputs (F3-F5), value check B (F9)
    rows = {
        n: design_row(json.loads((out / "observed" / f"{n}.json").read_text()))
        for n in obs
        if n.endswith("-primary")
    }
    spread = {}
    for f in FLOORS:
        adm = [r["worst_M"] for r in rows.values() if r["worst_M"] is not None
               and r["worst_M"] >= f and r["max_delta_p_pa"] <= 250]  # fmt: skip
        spread[f"{f:.2f}"] = {
            "admissible": len(adm),
            "worst_M_spread": (max(adm) - min(adm)) if len(adm) > 1 else None,
            "band": 0.05,
        }
    result["triage"] = {"designs": rows, "value_check_B": spread}
    # D5 cross-hardware: the cold-repeat pair against the panel's own q5 pair
    if "deep-dense-fresh-pair" in obs and "deep-dense-primary" in obs:
        a = json.loads((out / "observed/deep-dense-primary.json").read_text())
        b = json.loads((out / "observed/deep-dense-fresh-pair.json").read_text())
        sa, sb = a["scalars"]["scalar_q5_d0.5"], b["scalars"]["scalar_q5_d0.5"]
        fa, fb = a["flows"]["flow_q5"], b["flows"]["flow_q5"]
        dm, dp = sb["mixing"] - sa["mixing"], fb["delta_p_pa"] / fa["delta_p_pa"] - 1
        exact = abs(dm) <= 1e-9 and abs(dp) <= 1e-9
        result["parity"] = {
            "phi_bitwise_equal": fa["phi_data_sha256"] == fb["phi_data_sha256"],
            "T_bitwise_equal": sa["T_data_sha256"] == sb["T_data_sha256"],
            "delta_M": dm,
            "delta_p_rel": dp,
            "pass": bool(exact or (abs(dm) <= 1e-4 and abs(dp) <= 1e-4)),
            "flag": None if exact else "NONDETERMINISTIC",
        }
    # C1-C4 on this hardware (C5 from the committed periodic result)
    if periodic and {"smooth-controls-h10", "smooth-poiseuille-h7.071"} <= set(obs):
        result["controls"] = proof.controls(
            obs["smooth-controls-h10"], obs["smooth-poiseuille-h7.071"], periodic
        )
    (out / "judge.json").write_text(json.dumps(result, indent=1, default=float) + "\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--periodic", type=Path)
    args = parser.parse_args(argv)
    r = judge(args.cases, args.out, args.periodic)
    print(json.dumps({"observed": len(list((args.out / "observed").glob("*.json"))),
                      "observe_errors": sorted(r["observe_errors"])}))  # fmt: skip


if __name__ == "__main__":
    main()

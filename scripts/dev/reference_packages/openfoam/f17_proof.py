"""f17 feature and control proof on real OpenFOAM v2506 output.

    python3 f17_proof.py controls CTRL10 CTRL7 PERIODIC_RESULT.json --out C.json
    python3 f17_proof.py cache WITNESS FRESH FOREIGN_CASE --out R.json
    python3 f17_proof.py convergence PRIMARY REFINED --out D.json
    python3 f17_proof.py stages CASE...            (per-stage CPU-s from logs)

Every acceptance value is F17-SCIENCE-VALUES-01 (C1-C5, D1-D7), registered
before these runs. A failing check is reported as a finding, never re-banded.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f17_controls as ctl
import f17_extract as ex
import f17_foam as foam
import foam_run

DECISION = ".agent/decisions/2026-10-15-F17-SCIENCE-VALUES-01.md"
Q5 = 5e-9 / 60


def developed_gradient(case_dir, flow="flow_q5"):
    case = Path(case_dir)
    t = ex.latest_time(case / flow)
    p = foam.read_field(case / flow / t / "p")["internal"]
    x = foam.read_field(case / "mesh/constant/C")["internal"][:, 0]
    sel = (x > 0.002) & (x < 0.008)
    slope = np.polyfit(x[sel], p[sel], 1)[0]
    return -ex.RHO * slope, int(sel.sum())


def controls(ctrl10, ctrl7, periodic):
    o10, o7 = ex.observe(ctrl10), ex.observe(ctrl7)
    exact = ctl.developed_gradient_pa_m(Q5)
    g10, n10 = developed_gradient(ctrl10)
    g7, n7 = developed_gradient(ctrl7)
    e10, e7 = g10 / exact - 1, g7 / exact - 1
    order = math.log(abs(e10) / abs(e7)) / math.log(math.sqrt(2))
    c1 = {
        "exact_gradient_pa_m": exact,
        "h10": {
            "gradient_pa_m": g10,
            "rel_error": e10,
            "cells": n10,
            "flow": o10["flows"]["flow_q5"],
        },
        "h7.071": {
            "gradient_pa_m": g7,
            "rel_error": e7,
            "cells": n7,
            "flow": o7["flows"]["flow_q5"],
        },
        "observed_order": order,
        "band": {"h10": 0.03, "h7.071": 0.015, "order": [1.5, 2.5]},
    }
    c1["pass"] = bool(
        abs(e10) <= 0.03
        and abs(e7) <= 0.015
        and 1.5 <= order <= 2.5
        and o10["flows"]["flow_q5"]["converged"]
        and o7["flows"]["flow_q5"]["converged"]
    )
    s = o10["scalars"]
    uni = s["scalar_q5_d1_uniform"]
    t = ex.latest_time(Path(ctrl10) / "scalar_q5_d1_uniform")
    c = foam.read_field(Path(ctrl10) / "scalar_q5_d1_uniform" / t / "T")["internal"]
    c2 = {
        "max_abs_c_minus_1": float(np.abs(c - 1).max()),
        "solute_residual_fraction": uni["solute_residual_fraction"],
        "mixing": uni.get("mixing"),
        "band": {"max_abs_c_minus_1": 1e-6, "solute": 0.005},
    }
    c2["pass"] = bool(
        c2["max_abs_c_minus_1"] <= 1e-6 and uni["solute_ok"] and uni["converged"]
    )
    c3 = {}
    for name, q, d in (
        ("scalar_q1_d2", 1e-9 / 60, 2e-10),
        ("scalar_q5_d0.5", Q5, 0.5e-10),
    ):
        ref = ctl.reference_mixing(q, d)
        r = s[name]
        c3[name] = {
            "M_openfoam": r["mixing"],
            **ref,
            "delta_M": r["mixing"] - ref["M_ref"],
            "mean_c": r["mean_c"],
            "solute_residual_fraction": r["solute_residual_fraction"],
            "bounds": r["cell_c_min_max"],
            "converged": r["converged"],
        }
        c3[name]["pass"] = bool(
            abs(r["mixing"] - ref["M_ref"]) <= 0.01
            and ref["self_delta"] <= 1e-3
            and abs(r["mean_c"] - 0.5) <= 1e-3
            and r["solute_ok"]
            and r["bounds_ok"]
            and r["converged"]
        )
    z = s["scalar_q5_d0"]
    c4 = {
        "M": z["mixing"],
        "band": 1e-3,
        "bounds": z["cell_c_min_max"],
        "solute_residual_fraction": z["solute_residual_fraction"],
    }
    c4["pass"] = bool(z["mixing"] <= 1e-3 and z["converged"])
    c5 = json.loads(Path(periodic).read_text())
    return {
        "poiseuille": c1,
        "uniform": c2,
        "split": c3,
        "zeroD": c4,
        "periodic_scalar": {
            "orders": c5["metrics"],
            "band": [1.7, 2.3],
            "state": c5["state"],
            "pass": c5["state"] == "PASS",
        },
        "pass": all(x["pass"] for x in (c1, c2, c4, *c3.values()))
        and c5["state"] == "PASS",
        "decision": DECISION,
    }


def _scalar_dir(src, dst):
    """A fresh scalar case (inputs only) cloned from a frozen template."""
    dst = Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    for sub in ("system", "constant"):
        shutil.copytree(Path(src) / sub, dst / sub, symlinks=True)
    (dst / "0").mkdir()
    shutil.copy(Path(src) / "0" / "T", dst / "0" / "T")


def cache(witness, fresh, foreign):
    """D4-D6 on the deep-dense witness; FRESH holds an independent flow_q5 +
    scalar_q5_d0.5 run on the same frozen mesh; FOREIGN is another design's case."""
    w, f = Path(witness), Path(fresh)
    ow, of = ex.observe(w), ex.observe(f)
    tmpl = w / "scalar_q5_d0.5"
    # refusal cases: run_scalar must refuse before the solver starts
    tests = {}
    _scalar_dir(tmpl, w / "refuse_wrong_q")
    _scalar_dir(tmpl, w / "refuse_wrong_mesh")
    _scalar_dir(tmpl, w / "refuse_no_phi")
    _scalar_dir(tmpl, w / "refuse_altered_phi")
    _scalar_dir(tmpl, w / "fallback_no_phi")
    for name in ("flow_foreign", "flow_nophi", "flow_altered"):
        if (w / name).exists():
            shutil.rmtree(w / name)
    shutil.copytree(Path(foreign) / "flow_q5", w / "flow_foreign", symlinks=True)
    shutil.copytree(w / "flow_q5", w / "flow_nophi", symlinks=True)
    shutil.copytree(w / "flow_q5", w / "flow_altered", symlinks=True)
    t = (w / "flow_q5/receipt.txt").read_text().split("time ")[1].split()[0]
    (w / "flow_nophi" / t / "phi").unlink()
    blob = bytearray((w / "flow_altered" / t / "phi").read_bytes())
    blob[-200] ^= 0x01  # one bit inside the binary flux payload
    (w / "flow_altered" / t / "phi").write_bytes(bytes(blob))
    script = (
        "source functions.sh; source keys.sh; "
        'run_scalar refuse_wrong_q flow_q3 "$K5"; echo "wrong_q rc=$?"; '
        'run_scalar refuse_wrong_mesh flow_foreign "$K5"; echo "wrong_mesh rc=$?"; '
        'run_scalar refuse_no_phi flow_nophi "$K5"; echo "no_phi rc=$?"; '
        'run_scalar refuse_altered_phi flow_altered "$K5"; echo "altered rc=$?"; '
        "cp flow_q5/$(sed -n 's/^time //p' flow_q5/receipt.txt)/U fallback_no_phi/0/ && "
        "cd fallback_no_phi && ln -sfn ../../mesh/constant/polyMesh constant/polyMesh && "
        "scalarTransportFoam > log.scalarTransportFoam 2>&1; echo fallback_rc=$?"
    )
    row = foam_run.run(w, script, memory="3g", timeout=3600)
    for name in ("refuse_wrong_q", "refuse_wrong_mesh", "refuse_no_phi",
                 "refuse_altered_phi"):  # fmt: skip
        status = (w / name / "STATUS").read_text().strip() if (
            w / name / "STATUS").exists() else None  # fmt: skip
        tests[name] = {
            "status": status,
            "solver_started": (w / name / "log.scalarTransportFoam").exists(),
            "pass": bool(
                status
                and status.startswith("REFUSED")
                and not (w / name / "log.scalarTransportFoam").exists()
            ),
        }
    fb_t = ex.latest_time(w / "fallback_no_phi")
    fb_phi = ex.data_sha(w / "fallback_no_phi" / fb_t / "phi") if fb_t else None
    fb_log = (w / "fallback_no_phi/log.scalarTransportFoam").read_text()
    flow_phi = ow["flows"]["flow_q5"]["phi_data_sha256"]
    fallback = {
        "phi_recomputed_from_U": fb_phi != flow_phi,
        "would_be_caught_by_phi_check": fb_phi != flow_phi,
        "solver_log_says": "Reading/calculating face flux field phi" in fb_log,
    }
    reused = ow["scalars"]["scalar_q5_d0.5"]
    freshs = of["scalars"]["scalar_q5_d0.5"]
    parity = {
        "flow_phi_bitwise_equal": of["flows"]["flow_q5"]["phi_data_sha256"] == flow_phi,
        "T_bitwise_equal": freshs["T_data_sha256"] == reused["T_data_sha256"],
        "delta_M": freshs["mixing"] - reused["mixing"],
        "delta_p_rel": of["flows"]["flow_q5"]["delta_p_pa"]
        / ow["flows"]["flow_q5"]["delta_p_pa"]
        - 1,
        "fresh_flow_iterations": of["flows"]["flow_q5"]["iterations"],
    }
    exact = abs(parity["delta_M"]) <= 1e-9 and abs(parity["delta_p_rel"]) <= 1e-9
    parity["pass"] = bool(
        exact or (abs(parity["delta_M"]) <= 1e-4 and abs(parity["delta_p_rel"]) <= 1e-4)
    )
    parity["flag"] = None if exact else "NONDETERMINISTIC"
    one_way = {
        "scalar_phi_unchanged_all": all(
            r.get("phi_is_flow_phi") for r in ow["scalars"].values() if "mixing" in r
        ),
        "flow_solver_reads_c": False,
        "basis": "simpleFoam has no T field; scalarTransportFoam reads U, phi and "
        "never writes a changed phi (data hash equal to the flow receipt)",
    }
    one_way["pass"] = one_way["scalar_phi_unchanged_all"]
    return {
        "one_way": one_way,
        "parity": parity,
        "refusal": tests,
        "fallback_detection": fallback,
        "refusal_launch": {k: row[k] for k in ("wall_s", "cgroup_cpu_s", "exit")},
        "pass": bool(
            one_way["pass"]
            and parity["pass"]
            and all(x["pass"] for x in tests.values())
            and fallback["would_be_caught_by_phi_check"]
        ),
        "flow_reuse_accepted": None,
        "decision": DECISION,
    }


def convergence(primary, refined):
    a, b = ex.observe(primary), ex.observe(refined)
    key = "scalar_q5_d0.5"
    ma, mb = a["scalars"][key]["mixing"], b["scalars"][key]["mixing"]
    pa, pb = a["flows"]["flow_q5"]["delta_p_pa"], b["flows"]["flow_q5"]["delta_p_pa"]
    d1 = {
        "M_primary": ma,
        "M_refined": mb,
        "delta_M": mb - ma,
        "delta_p_pa": [pa, pb],
        "delta_p_rel": pb / pa - 1,
        "volume_rel_error": [
            a["mesh"]["volume_rel_error"],
            b["mesh"]["volume_rel_error"],
        ],
        "band": {"M": 0.02, "p": 0.05, "volume": 0.005},
    }
    d1["pass"] = bool(
        abs(d1["delta_M"]) <= 0.02
        and abs(d1["delta_p_rel"]) <= 0.05
        and a["mesh"]["volume_ok"]
        and b["mesh"]["volume_ok"]
    )
    d2 = {}
    for rung, o in (("primary", a), ("refined", b)):
        m0 = o["scalars"]["scalar_q5_d0"]["mixing"]
        mmin = o["scalars"][key]["mixing"]
        d2[rung] = {
            "M_D0": m0,
            "M_Dmin": mmin,
            "difference": mmin - m0,
            "pass": bool(mmin - m0 >= 0.02),
        }
    d2["verdict"] = (
        "PRIMARY_ADEQUATE"
        if d2["primary"]["pass"]
        else "REFINED_RUNG_REQUIRED"
        if d2["refined"]["pass"]
        else "HIGH_PE_UNRESOLVED"
    )
    diag = a["scalars"].get("scalar_q5_d0.5_limitedLinear01")
    d3 = None
    if diag:
        d3 = {
            "M_limitedLinear01": diag.get("mixing"),
            "iterations": diag["iterations"],
            "converged": diag["converged"],
            "M_span_last10": diag["M_span_last10"],
            "M_linearUpwind": ma,
            "role": "DIAGNOSTIC",
        }
    return {
        "design": a["design"],
        "label": a["label"],
        "two_mesh": d1,
        "high_pe": d2,
        "scheme_diagnostic": d3,
        "decision": DECISION,
    }


def stages(case_dir):
    """Per-solver CPU (OpenFOAM ExecutionTime) and iterations, from logs."""
    out = {}
    for log in sorted(Path(case_dir).glob("**/log.*")):
        text = log.read_text(errors="replace")
        times = re.findall(r"ExecutionTime = ([\d.]+) s\s+ClockTime = ([\d.]+) s", text)
        if times:
            out[str(log.relative_to(case_dir))] = {
                "cpu_s": float(times[-1][0]),
                "clock_s": float(times[-1][1]),
            }
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, nargs in (("controls", 3), ("cache", 3), ("convergence", 2)):
        p = sub.add_parser(name)
        p.add_argument("paths", nargs=nargs)
        p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("stages")
    p.add_argument("paths", nargs="+")
    args = parser.parse_args(argv)
    if args.cmd == "stages":
        print(json.dumps({c: stages(c) for c in args.paths}, indent=1))
        return
    fn = {"controls": controls, "cache": cache, "convergence": convergence}[args.cmd]
    result = fn(*args.paths)
    args.out.write_text(json.dumps(result, indent=1, default=float) + "\n")
    print(
        json.dumps(
            {k: v.get("pass") if isinstance(v, dict) else v for k, v in result.items()},
            default=str,
        )
    )


if __name__ == "__main__":
    main()

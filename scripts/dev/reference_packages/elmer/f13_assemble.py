"""Assemble f13-proof-v2.json from solved local case directories.

    python -m scripts.dev.reference_packages.elmer.f13_assemble --work DIR --out EVIDENCE.json

Reads only solved outputs (ports.dat/.names, deck.json, cost.json) under
DIR and judges each registered check of F13-SCIENCE-VALUES-01 with the
bands it fixed before the runs. Missing runs are reported NOT_RUN, never
PASS. Layout under DIR: v2/<case> (controls, primaries, separate solves,
5 Hz witness), solvers/nominal-{direct,iterative} (D5), lead100/<label>
(D2), mesh4/<label> (D1), mm.json (mode matching), mms.json (B1).
"""

from __future__ import annotations

import argparse
import cmath
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.challenge_pipeline import silencer_readiness as sr
from scripts.dev.reference_packages.elmer import f13_deck as deck
from scripts.dev.reference_packages.elmer import f13_proof as p

OFFSET = ("nominal", "large-offset", "clearance-boundary")
COAXIAL = ("control-chamber", "small-coaxial", "short-neck-wide", "long-neck-small")


def _rows(d):
    d = Path(d)
    if not (d / "ports.dat").exists() or not (d / "cost.json").exists():
        return None
    cost = json.loads((d / "cost.json").read_text())
    if cost.get("solve", {}).get("exit") != 0:
        return None
    return p.observe(d)


def _cost(d):
    c = json.loads((Path(d) / "cost.json").read_text())
    s = c["solve"]
    return {"nodes": c.get("nodes"), "frequency_systems": c["frequency_systems"],
            "solve_cpu_s": s["cpu_s"], "solve_wall_s": s["wall_s"], "peak_mib": s["peak_mib"],
            "mesh_cpu_s": c.get("mesh", {}).get("cpu_s"), "mesh_wall_s": c.get("mesh", {}).get("wall_s"),
            "cpu_s_per_frequency": c.get("cpu_s_per_frequency"), "outcome": s["outcome"]}  # fmt: skip


def _status(ok):
    return "PASS" if ok else "FAIL"


def assemble(work, out):
    work = Path(work)
    v2 = work / "v2"
    doc = {
        "schema": "carbon.reference-package.f13-feature-proof.v2",
        "decision": sr.VALUES_DECISION,
        "scope": "PUBLIC_DEVELOPMENT engineering evidence; no qualification, Tier 2 or LIVE claim",
        "image": sr.IMAGE,
        "mesh_image": deck.MESH_IMAGE,
        "deck_version": deck.DECK_VERSION,
        "deck_sha256": sr.DECK_SHA,
        "observer": sr.PINS["observer"],
        "linear_solver": sr.PINS["linear_solver"],
        "host_profile": p.HOST_PROFILE,
        "checks": {},
    }
    checks = doc["checks"]

    # B1 MMS
    mms = work / "mms.json"
    if mms.exists():
        m = json.loads(mms.read_text())
        doc["mms"] = {"evidence": "f13-helmholtz-mms.json", "finest_pair": m["finest_pair"],
                      "rows": [{k: r.get(k) for k in ("h_nominal", "nodes", "l2_real", "h1_real", "l2_imag", "h1_imag", "solver")}
                               for r in m["rows"]], "pass": m["pass"]}  # fmt: skip
        checks["B1_mms"] = _status(m["pass"])
    elif (work / "mms-partial.json").exists():
        doc["mms_partial"] = json.loads((work / "mms-partial.json").read_text())
        checks["B1_mms"] = "DEFERRED_TO_POD"
    else:
        checks["B1_mms"] = "NOT_RUN"

    # B2 straight duct
    got = _rows(v2 / "control-duct")
    if got:
        rows, _ = got
        k = [2 * math.pi * r["frequency_hz"] / deck.C for r in rows]
        dt = max(
            abs(complex(*r["t"]) - cmath.exp(-1j * kk * 0.12)) for r, kk in zip(rows, k)
        )
        dr = max(abs(complex(*r["r"])) for r in rows)
        tl = max(abs(r["tl_db"]) for r in rows)
        s = p.summary(rows)
        ok = (tl <= 0.25 and dt <= 0.03 and dr <= 0.03
              and s["max_abs_plane_residual"] <= sr.POWER_PLANE_BAND
              and s["max_abs_integral_residual"] <= sr.POWER_INTEGRAL_BAND)  # fmt: skip
        doc["straight_duct"] = {"frequencies": len(rows), "max_abs_tl_db": tl,
                                "max_abs_t_minus_exact": dt, "max_abs_r": dr,
                                "max_abs_plane_residual": s["max_abs_plane_residual"],
                                "max_abs_integral_residual": s["max_abs_integral_residual"],
                                "bands": {"tl_db": 0.25, "t": 0.03, "r": 0.03}, "pass": ok}  # fmt: skip
        checks["B2_straight_duct"] = _status(ok)
    else:
        checks["B2_straight_duct"] = "NOT_RUN"

    # B3 coaxial vs mode matching; B4 TMM diagnostic
    mm_path = work / "mm.json"
    mm = json.loads(mm_path.read_text()) if mm_path.exists() else {}
    doc["coaxial_mode_matching"] = {}
    all_ok, ran = True, 0
    for name in COAXIAL:
        case_dir = v2 / (name if name.startswith("control") else f"{name}-primary")
        got = _rows(case_dir)
        if not got or name not in mm:
            doc["coaxial_mode_matching"][name] = "DEFERRED_TO_POD"
            continue
        ran += 1
        rows, _ = got
        cmp_ = p.compare(rows, mm[name]["n40"], p.MESH_TL_DB)
        conv = mm[name]["conv_max_dtl_db_resolved"] <= 0.05
        cmp_["mode_matching_convergence_n20_vs_n40_db"] = mm[name][
            "conv_max_dtl_db_resolved"
        ]
        cmp_["mode_matching_converged"] = conv
        cmp_["pass"] = cmp_["pass"] and conv
        cmp_["fem_p10_db"] = p.summary(rows)["p10_tl_db"]
        all_ok &= cmp_["pass"]
        doc["coaxial_mode_matching"][name] = cmp_
    checks["B3_coaxial_mode_matching"] = (
        _status(all_ok)
        if ran == len(COAXIAL)
        else ("FAIL" if not all_ok and ran else "NOT_RUN")
    )
    # B3 diagnostic (not a registered check): panel coaxials on the 4 mm mesh
    diag = {}
    for name in COAXIAL[1:]:
        got = _rows(work / "coax4" / name)
        if got and name in mm:
            c = p.compare(got[0], mm[name]["n40"], p.MESH_TL_DB)
            diag[name] = {k: c[k] for k in ("common_frequencies", "max_abs_dtl_db_resolved",
                                            "dp10_db", "dmean_db", "pass")}  # fmt: skip
            diag[name]["cost"] = _cost(work / "coax4" / name)
    if diag:
        doc["coaxial_mode_matching_4mm_diagnostic"] = diag
    got = _rows(v2 / "control-chamber")
    if got:
        rows, _ = got
        diffs = {int(r["frequency_hz"]): r["tl_db"] - deck.chamber_tl(r["frequency_hz"], 62.5, 75.0)
                 for r in rows if int(r["frequency_hz"]) % 250 == 0}  # fmt: skip
        doc["transfer_matrix_diagnostic"] = {
            "role": "DIAGNOSTIC (B4): no in-band acceptance; mode matching (B3) is the acceptance control",
            "fem_minus_tmm_db_every_250hz": diffs,
        }

    # C1-C3 power/passivity over every solved v2 case
    power, ok_all = {}, True
    for d in sorted(x for x in v2.iterdir() if x.is_dir()):
        got = _rows(d)
        if not got:
            continue
        rows, finding = got
        s = p.summary(rows)
        power[d.name] = {"max_abs_plane_residual": s["max_abs_plane_residual"],
                         "max_abs_integral_residual": s["max_abs_integral_residual"],
                         "finding": finding}  # fmt: skip
        ok_all &= not finding
    doc["power_passivity"] = {"bands": {"plane": sr.POWER_PLANE_BAND, "integral": sr.POWER_INTEGRAL_BAND},
                              "cases": power}  # fmt: skip
    checks["C_power_passivity"] = _status(ok_all) if power else "NOT_RUN"

    # D4 scan vs separate
    got = _rows(v2 / "nominal-primary")
    if got:
        scan = {r["frequency_hz"]: r for r in got[0]}
        par, ok = {}, True
        for f in (500.0, 1500.0, 2500.0):
            single = _rows(v2 / f"nominal-single-{f:g}")
            if not single:
                ok = False
                par[str(int(f))] = "NOT_RUN"
                continue
            a, b = scan[f], single[0][0]
            dtl = abs(a["tl_db"] - b["tl_db"])
            dt = abs(complex(*a["t"]) - complex(*b["t"]))
            par[str(int(f))] = {"scan_tl_db": a["tl_db"], "separate_tl_db": b["tl_db"],
                                "abs_dtl_db": dtl, "abs_dt": dt}  # fmt: skip
            ok &= dtl <= p.PARITY_TL_DB and dt <= p.PARITY_T_ABS
        doc["scan_parity"] = {
            "case": "nominal v2",
            **par,
            "bands": {"tl_db": p.PARITY_TL_DB, "t": p.PARITY_T_ABS},
            "pass": ok,
        }
        checks["D4_scan_parity"] = _status(ok)
    else:
        checks["D4_scan_parity"] = "NOT_RUN"

    # D5 iterative vs direct
    a, b = (
        _rows(work / "solvers/nominal-iterative"),
        _rows(work / "solvers/nominal-direct"),
    )
    if a and b:
        par, ok = {}, True
        for ra, rb in zip(a[0], b[0]):
            dtl = abs(ra["tl_db"] - rb["tl_db"])
            dt = abs(complex(*ra["t"]) - complex(*rb["t"]))
            par[str(int(ra["frequency_hz"]))] = {"abs_dtl_db": dtl, "abs_dt": dt}
            ok &= dtl <= p.PARITY_TL_DB and dt <= p.PARITY_T_ABS
        doc["solver_parity"] = {"case": "nominal v2, 500/1500/2500 Hz, same mesh", **par,
                                "cost_direct": _cost(work / "solvers/nominal-direct"),
                                "cost_iterative": _cost(work / "solvers/nominal-iterative"),
                                "pass": ok}  # fmt: skip
        checks["D5_solver_parity"] = _status(ok)
    else:
        checks["D5_solver_parity"] = "NOT_RUN"

    # D2 lead 60 vs 100 mm; D1 mesh 8 vs 4 mm (common frequencies)
    for key, sub, band, cband in (("D2_lead_60_vs_100mm", "lead100", p.LEAD_TL_DB, p.LEAD_T_ABS),
                                  ("D1_mesh_8_vs_4mm", "mesh4", p.MESH_TL_DB, None)):  # fmt: skip
        res, ok, ran = {}, True, 0
        for label in OFFSET:
            base_dir = v2 / f"{label}-primary"
            if not (base_dir / "cost.json").exists():
                base_dir = v2 / f"{label}-sub50"
            base, other = _rows(base_dir), _rows(work / sub / label)
            if not base or not other:
                res[label] = "NOT_RUN"
                ok = False
                continue
            ran += 1
            c = p.compare(base[0], other[0], band, cband)
            c["other_finding"] = other[1]
            c["other_cost"] = _cost(work / sub / label)
            ok &= c["pass"] and not other[1]
            res[label] = c
        doc[key] = res
        checks[key] = (
            _status(ok)
            if ran == len(OFFSET)
            else (
                "FAIL"
                if ran
                and not ok
                and any(isinstance(v, dict) and not v["pass"] for v in res.values())
                else ("DEFERRED_TO_POD" if ran else "NOT_RUN")
            )
        )

    # D3 frequency grid (clearance-boundary 10 Hz vs 5 Hz)
    a, b = (
        _rows(v2 / "clearance-boundary-primary"),
        _rows(v2 / "clearance-boundary-freq5hz"),
    )
    if a and b:
        c = p.frequency_refinement(a[0], b[0])
        doc["D3_frequency_10_vs_5hz"] = {"case": "clearance-boundary", **c}
        checks["D3_frequency_10_vs_5hz"] = _status(c["pass"])
    else:
        checks["D3_frequency_10_vs_5hz"] = "DEFERRED_TO_POD"

    # primaries: curve summaries and cost
    doc["primaries"] = {}
    for d in sorted(v2.glob("*-primary")):
        got = _rows(d)
        if got:
            doc["primaries"][d.name.removesuffix("-primary")] = {
                **p.summary(got[0]),
                "cost": _cost(d),
            }
    doc["costs"] = {d.name: _cost(d) for d in sorted(v2.iterdir())
                    if (d / "cost.json").exists() and json.loads((d / "cost.json").read_text()).get("solve")}  # fmt: skip
    doc["all_pass"] = bool(checks) and all(v == "PASS" for v in checks.values())
    doc["assembler_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    Path(out).write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f13_assemble")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    doc = assemble(args.work, args.out)
    print(json.dumps(doc["checks"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

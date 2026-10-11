"""Lid-spreading pre-solve and the cooling value check (registry
cooling-feasibility-02/lid-spreading-registry.json). DEVELOPMENT screen.

    python -m scripts.dev.cold_plate.lid_spreading --cfeas DIR --plan PLAN --out OUT.json

Step 1, exact 2D lid conduction (Fourier-cosine in x, closed form through
the thickness): top flux q(x) (the registered axial band, normalised to the
footprint power), adiabatic ends, bottom Robin to the local coolant bulk
through TIM2 and the cell in series, U = 1 / (R2 + 1/h_cell). For mode n
(k_n = n pi / L), with the sink's mode Tb_n:

    q_b,n = (q_n - k k_n Tb_n sinh(k_n t)) / (cosh(k_n t) + (k k_n / U) sinh(k_n t))

and q_b,0 = q_0 (energy conservation). Step 2 predicts each existing cell
design's interface peak per stratum from its own warm solves.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.cold_plate import domain

L = 0.030
NX = 3000
MODES = 200
P_W, INLET_C = 1500.0, 45.0
NOMINAL = {"t_mm": 1.5, "k": 391.0, "R1": 5.14e-6, "R2": 6e-6}
LIMIT_C = 85.0
STRATA = {
    "cold_uniform": {"inlet_c": 30.0, "p_w": 500.0, "ratio": 1.0, "centre_mm": 15.0},
    "typical_uniform": {
        "inlet_c": 40.0,
        "p_w": 1000.0,
        "ratio": 1.0,
        "centre_mm": 15.0,
    },
    "warm_uniform": {"inlet_c": 45.0, "p_w": 1500.0, "ratio": 1.0, "centre_mm": 15.0},
    "warm_central_band": {
        "inlet_c": 45.0,
        "p_w": 1500.0,
        "ratio": 3.0,
        "centre_mm": 15.0,
    },
    "warm_outlet_band": {
        "inlet_c": 45.0,
        "p_w": 1500.0,
        "ratio": 3.0,
        "centre_mm": 24.0,
    },
}
#: Existing cell strata that supply each value-check stratum's face response.
CELL_STRATUM = {
    "warm_central_band": "warm_central_hotspot",
    "warm_outlet_band": "warm_outlet_hotspot",
}


def raw_flux(p_w, ratio, centre_mm, width_mm=2.5):
    case = {
        "channel_width_mm": 0.3, "fin_width_mm": 0.3, "channel_depth_mm": 2.0,
        "flow_lpm_per_kw": 2.0, "inlet_c": 45.0, "heat_load_w": p_w,
        "hotspot_ratio": ratio, "hotspot_center_mm": centre_mm, "hotspot_width_mm": width_mm,
    }  # fmt: skip
    x = (np.arange(NX) + 0.5) * L / NX
    return x, np.array([domain.heat_flux(case, xi * 1e3) for xi in x])


def coolant_rise(p_w):
    t = domain.K0 + 45.0
    flow = p_w / 1000.0 * 2.0 / 60000.0
    return p_w / (domain.pg25("rho", t) * flow * domain.pg25("cp", t))


def presolve(q, x, t_mm, k, r2, h_cell, rise_k):
    """Post-spreader flux q_b(x) at the TIM2 plane."""
    t = t_mm * 1e-3
    u = 1.0 / (r2 + 1.0 / h_cell)
    dx = L / NX
    out = np.full_like(q, q.mean())
    for n in range(1, MODES + 1):
        kn = n * math.pi / L
        c = np.cos(kn * x)
        qn = 2.0 / L * np.sum(q * c) * dx
        # sink T_b = rise x / L: cosine coefficient 2 L ((-1)^n - 1) / (n pi)^2, times rise / L
        tbn = 2.0 * ((-1) ** n - 1) / (n * math.pi) ** 2 * rise_k
        a = kn * t
        if a > 600:  # deep modes decay completely through the lid
            break
        qbn = (qn - k * kn * tbn * math.sinh(a)) / (
            math.cosh(a) + (k * kn / u) * math.sinh(a)
        )
        out += qbn * c
    return out


def h_cells(cfeas):
    """Per design: mean cell conductance h = q / (T_face - T_bulk) from the
    warm uniform solve, and its span-mean face profiles per stratum."""
    out = {}
    for line in Path(cfeas, "records.jsonl").read_text().splitlines():
        r = json.loads(line)
        out.setdefault(r["design_id"], {})[r["stratum"]] = r
    return out


def design_h(rec):
    o, d = rec["outputs"], rec["derived"]
    prof = np.array(o["profile_c"])
    xs = (np.arange(len(prof)) + 0.5) / len(prof)
    bulk = rec["inputs"]["inlet_c"] + (o["outlet_c"] - rec["inputs"]["inlet_c"]) * xs
    return float(np.mean(d["heat_flux_w_m2"] / (prof - bulk))), prof


def main(cfeas, out):
    designs = h_cells(cfeas)
    hs = {}
    for did, recs in designs.items():
        u = recs.get("warm_uniform")
        if u and u["status"] == "OK":
            hs[did] = design_h(u)[0]
    h_med = float(np.median(list(hs.values())))
    h_lo, h_hi = float(min(hs.values())), float(max(hs.values()))
    rise = coolant_rise(P_W)
    step1 = {"h_cell_w_m2k": {"median": h_med, "min": h_lo, "max": h_hi, "designs": len(hs)},
             "coolant_rise_k": rise, "maps": {}}  # fmt: skip
    for name, centre in (("central_15mm", 15.0), ("outlet_24mm", 24.0)):
        x, q = raw_flux(P_W, 3.0, centre)
        rows = {}

        def ratio(
            t_mm=NOMINAL["t_mm"], k=NOMINAL["k"], r2=NOMINAL["R2"], h=h_med, x=x, q=q
        ):
            qb = presolve(q, x, t_mm, k, r2, h, rise)
            i = int(np.argmax(qb))
            return {"peak_over_mean": float(qb.max() / qb.mean()), "peak_x_mm": float(x[i] * 1e3),
                    "tim2_jump_peak_k": float(r2 * qb.max())}  # fmt: skip

        rows["nominal"] = ratio()
        rows["raw_peak_over_mean"] = float(q.max() / q.mean())
        rows["sensitivity"] = {
            "t_mm": {
                str(v): ratio(t_mm=v)["peak_over_mean"] for v in (1.5, 2.0, 2.5, 3.2)
            },
            "k": {str(v): ratio(k=v)["peak_over_mean"] for v in (380.0, 391.0, 400.0)},
            "R2": {str(v): ratio(r2=v)["peak_over_mean"] for v in (4e-6, 6e-6, 8e-6)},
            "h_cell": {
                f"{v:.0f}": ratio(h=v)["peak_over_mean"] for v in (h_lo, h_med, h_hi)
            },
        }
        corners = []
        for t_mm in (1.5, 3.2):
            for k in (380.0, 400.0):
                for r2 in (4e-6, 8e-6):
                    for h in (h_lo, h_hi):
                        corners.append({"t_mm": t_mm, "k": k, "R2": r2, "h": h,
                                        "peak_over_mean": ratio(t_mm, k, r2, h)["peak_over_mean"]})  # fmt: skip
        rows["corners_min_max"] = [
            min(c["peak_over_mean"] for c in corners),
            max(c["peak_over_mean"] for c in corners),
        ]
        rows["target_at_nominal_R2"] = 1.2
        step1["maps"][name] = rows

    # Step 2: value check per design and stratum.
    step2 = {}
    r2 = NOMINAL["R2"]
    for sname, s in STRATA.items():
        verdicts = {}
        for did, recs in designs.items():
            u = recs.get("warm_uniform")
            if not u or u["status"] != "OK":
                verdicts[did] = {
                    "verdict": "UNRESOLVED",
                    "why": "warm uniform cell outside reference applicability",
                }
                continue
            h, prof_u = design_h(u)
            scale = s["p_w"] / P_W
            qbar = s["p_w"] / L**2
            if s["ratio"] == 1.0:
                face = s["inlet_c"] + (prof_u - INLET_C) * scale
                qb_max = qbar  # uniform map stays uniform through the lid
                peak = float(np.max(face)) + r2 * qb_max
            else:
                cell = recs.get(CELL_STRATUM[sname])
                x, q = raw_flux(s["p_w"], s["ratio"], s["centre_mm"])
                qb = presolve(
                    q, x, NOMINAL["t_mm"], NOMINAL["k"], r2, h, coolant_rise(s["p_w"])
                )
                beta = (qb.max() / qb.mean() - 1.0) / (s["ratio"] - 1.0)
                if not cell or cell["status"] != "OK":
                    verdicts[did] = {"verdict": "UNRESOLVED", "why": "hotspot cell outside reference applicability",
                                     "post_peak_over_mean": float(qb.max() / qb.mean())}  # fmt: skip
                    continue
                prof_h = np.array(cell["outputs"]["profile_c"])
                face = prof_u + beta * (prof_h - prof_u)
                xs = (np.arange(len(face)) + 0.5) * L / len(face)
                qb_seg = np.interp(xs, x, qb)
                peak = float(np.max(face + r2 * qb_seg))
            margin = LIMIT_C - peak
            verdict = "PASS" if margin > 2 else ("FAIL" if margin < -2 else "NEAR")
            verdicts[did] = {
                "verdict": verdict,
                "interface_peak_c": peak,
                "margin_k": margin,
            }
        counts = {
            v: sum(1 for d in verdicts.values() if d["verdict"] == v)
            for v in ("PASS", "NEAR", "FAIL", "UNRESOLVED")
        }
        margins = [d["margin_k"] for d in verdicts.values() if "margin_k" in d]
        step2[sname] = {"counts": counts, "margin_range_k": [min(margins), max(margins)] if margins else None,
                        "non_trivial": counts["PASS"] > 0 and (counts["FAIL"] + counts["NEAR"]) > 0,
                        "designs": verdicts}  # fmt: skip
    valuable = any(v["non_trivial"] for v in step2.values())
    document = {"schema": "carbon.cooling.lid-spreading-presolve.v1", "nominal": NOMINAL,
                "step1": step1, "step2": step2, "valuable": valuable}  # fmt: skip
    Path(out).write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    return document


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="lid_spreading")
    parser.add_argument("--cfeas", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    doc = main(args.cfeas, args.out)
    print(json.dumps(doc["step1"], indent=1))
    for k, v in doc["step2"].items():
        print(
            k,
            v["counts"],
            "margins",
            v["margin_range_k"] and [round(m, 1) for m in v["margin_range_k"]],
            "non_trivial",
            v["non_trivial"],
        )
    print("VALUABLE:", doc["valuable"])

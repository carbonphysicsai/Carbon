"""The five registered set-A verification controls
(cooling-feasibility-02/panel-setA-registry.json, "controls").

    python -m scripts.dev.cold_plate.panel_setA_controls zero-load --out DIR
    python -m scripts.dev.cold_plate.panel_setA_controls score --jobs DIR --zero DIR --elmer-image ID --out JSON

ZERO_LOAD             cell + lid with no source at the warm inlet: the
                      solver's net enthalpy flow and the temperature drift
                      from the inlet (energy <= 1e-6 W per cell). The cell
                      analysis divides by the applied heat, so this control
                      reads the solver's enthalpy flows directly.
UNIFORM_1D_STACK      uniform map through `lid`: lid jump q t / k and TIM2
                      jump q R2'' against the closed form (<= 0.05 K).
FOURIER_CONDUCTION    `lid` against the pinned Elmer lid solve (set-A lid:
                      k 3000 W/mK, 3 mm, TIM2 R2'' in series with the
                      h-model film, linear sink, central ratio-3 band).
CONTACT_SIGN_ORIENTATION  every converged job: the interface peak is the face
                      plus R2'' q_b with the flux into the cell positive
                      (q_b > 0 and interface >= face everywhere it is read).
CONSERVATIVE_MAP_TRANSFER  every converged job: the cell's applied heat (the
                      60-mode series mean) against the lid's bottom-flux
                      integral (<= 0.1 %).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.cold_plate import analysis, openfoam
from scripts.dev.cold_plate import feasibility02 as cf
from scripts.dev.cold_plate import lid_spreading as ls
from scripts.dev.cold_plate import lid_spreading_elmer as lse
from scripts.dev.cold_plate import panel_setA as pa
from scripts.dev.cold_plate.reference import run_batch

ZERO_DESIGN, ZERO_CONTEXT = "w0.3-d6", "warm_uniform"
LIMITS = {"zero_load_w": 1e-6, "uniform_k": 0.05, "map_transfer_rel": 1e-3}
H_FILM = 55000.0  # the h-model film used to start every coupled job


def zero_load(out):
    out = Path(out)
    design, ctx = pa.DESIGNS[ZERO_DESIGN], pa.CONTEXTS[ZERO_CONTEXT]
    inputs = pa.cell_inputs(design, ctx)
    with cf.variant(design["base_mm"]), pa.cell_map(0.0, np.zeros(pa.CELL_MODES)):
        openfoam.write_case(inputs, out)
        status, wall, detail = run_batch.solve(
            out, "carbon-setA-control-zero-load", 1, 14400
        )
    record = {"status": status or "RAN", "wall_s": round(wall, 1), "run": detail}
    if status is None:
        t = max((x for x in (out / "times").read_text().split() if x != "0"), key=float)
        net = analysis._surface_value(out, "enthalpyOut", t) + analysis._surface_value(
            out, "enthalpyIn", t
        )
        t_in = analysis.K0 + ctx["inlet_c"]
        drift = max(
            abs(v - t_in)
            for region in ("fluid", "solid")
            for v in analysis.internal_field(out / t / region / "T")
        )
        lid_qb, lid_bottom, lid_top = pa.lid(
            np.zeros(pa.NX), np.full(pa.NX, ctx["inlet_c"])
        )
        record.update(
            net_enthalpy_w=net, cell_drift_k=drift,
            lid_drift_k=float(max(np.abs(lid_bottom - ctx["inlet_c"]).max(), np.abs(lid_top - ctx["inlet_c"]).max())),
            lid_flux_max_w_m2=float(np.abs(lid_qb).max()),
        )  # fmt: skip
        record["pass"] = (
            abs(net) <= LIMITS["zero_load_w"] and record["lid_flux_max_w_m2"] == 0.0
        )
    (out / "control.json").write_text(json.dumps(record, indent=1) + "\n")
    return record


def uniform_1d():
    q = 1500.0 / pa.L**2
    sink = np.full(pa.NX, 40.0)
    qb, bottom, top = pa.lid(np.full(pa.NX, q), sink)
    lid_jump = float(np.max(np.abs((top - bottom) - q * pa.LID_T_MM * 1e-3 / pa.LID_K)))
    tim_jump = float(np.max(np.abs((bottom - sink) - q * pa.R2)))
    return {"lid_jump_err_k": lid_jump, "tim2_jump_err_k": tim_jump, "flux_err_rel": float(np.max(np.abs(qb / q - 1))),
            "pass": max(lid_jump, tim_jump) <= LIMITS["uniform_k"]}  # fmt: skip


def fourier(out, image):
    """Elmer: Robin bottom with u = 1/(R2 + 1/h) to the linear sink. The
    series gets the same law as R2_eff = R2 + 1/h and the same sink."""
    elmer = lse.run(out, image, t_mm=pa.LID_T_MM, k=pa.LID_K, r2=pa.R2, h=H_FILM)
    x, q = ls.raw_flux(ls.P_W, 3.0, 15.0)
    q_raw = np.interp(pa.X, x, q)
    _, t_in, rise = lse.write(
        Path(out) / "series-inputs", pa.LID_T_MM, pa.LID_K, pa.R2, H_FILM
    )
    sink = t_in + rise * pa.X / pa.L
    qb, _, _ = pa.lid(q_raw, sink, r2=pa.R2 + 1.0 / H_FILM, modes=800)
    series = {
        "peak_over_mean": float(qb.max() / qb.mean()),
        "peak_x_mm": float(pa.X[int(np.argmax(qb))] * 1e3),
    }
    return {"elmer": elmer, "series": series,
            "peak_over_mean_rel_diff": abs(series["peak_over_mean"] / elmer["peak_over_mean"] - 1)}  # fmt: skip


def per_job(jobs_dir):
    rows = {}
    for path in sorted(Path(jobs_dir).glob("*/job.json")):
        job = json.loads(path.read_text())
        v = job.get("verdict_inputs")
        if not v:
            continue
        rows[job["job"]["job_id"]] = {
            "map_transfer_rel": v["map_transfer_rel"],
            "tim2_jump_peak_k": v["tim2_jump_peak_k"],
            "contact_sign_ok": v["tim2_jump_peak_k"] > 0
            and v["post_peak_over_mean"] >= 1.0,
        }
    return {
        "jobs": len(rows),
        "map_transfer_max_rel": max(
            (r["map_transfer_rel"] for r in rows.values()), default=None
        ),
        "map_transfer_pass": all(
            r["map_transfer_rel"] <= LIMITS["map_transfer_rel"] for r in rows.values()
        ),
        "contact_sign_pass": all(r["contact_sign_ok"] for r in rows.values()),
        "rows": rows,
    }


def score(jobs_dir, zero_dir, image, out):
    zero = json.loads((Path(zero_dir) / "control.json").read_text())
    jobs = per_job(jobs_dir)
    four = fourier(Path(out).parent / "controls-fourier", image)
    document = {
        "schema": "carbon.cooling.setA-controls.v1",
        "limits": LIMITS,
        "ZERO_LOAD": zero,
        "UNIFORM_1D_STACK": uniform_1d(),
        "FOURIER_CONDUCTION": four,
        "CONTACT_SIGN_ORIENTATION": {
            "pass": jobs["contact_sign_pass"],
            "jobs": jobs["jobs"],
        },
        "CONSERVATIVE_MAP_TRANSFER": {
            "pass": jobs["map_transfer_pass"],
            "max_rel": jobs["map_transfer_max_rel"],
        },
    }
    Path(out).write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    return document


def main(argv=None):
    parser = argparse.ArgumentParser(prog="panel_setA_controls")
    parser.add_argument("command", choices=("zero-load", "score"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--jobs", type=Path)
    parser.add_argument("--zero", type=Path)
    parser.add_argument("--elmer-image")
    args = parser.parse_args(argv)
    if args.command == "zero-load":
        print(json.dumps(zero_load(args.out)))
    else:
        doc = score(args.jobs, args.zero, args.elmer_image, args.out)
        print(
            json.dumps(
                {k: v.get("pass") for k, v in doc.items() if isinstance(v, dict)}
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

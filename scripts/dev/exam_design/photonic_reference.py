"""Passive reciprocal 3D photonic coupler reference (fdtdx), feasibility stage.

Public/synthetic DEVELOPMENT research. The reference is fdtdx 0.6.2's 3D FDTD
under the configuration below; agreement with it is agreement with that
configuration, not with a fabricated device.

Geometry family (one parent case = one geometry and its whole spectrum):

* two silicon strip waveguides, 500 nm x 220 nm, in silica cladding;
* a straight coupling section of length ``length_um`` at edge-to-edge
  ``gap_nm``; cosine S-bends separate the guides to ``port_pitch_um`` centre
  spacing at both ends, so every port plane sees one isolated waveguide. The
  left bends are 3.0 um and the right bends 2.0 um: the device is deliberately
  not mirror-symmetric in x, so ``S31 = S13`` is a reciprocity test rather than
  a symmetry identity;
* bounds: gap 150-300 nm, length 1-6 um.

Material model: non-dispersive, n_Si = 3.48 and n_SiO2 = 1.444 across the band
(a declared simplification, not a claim about real dispersion).

Port convention: ports 1 (upper) and 2 (lower) on the left, 3 (upper) and 4
(lower) on the right; fundamental TE mode. ``S[j,i]`` is the mode-overlap
amplitude at port ``j`` for unit injection at port ``i``, as fdtdx's
``calculate_sparam`` normalizes it (by the input-normalization detector at the
source). Excitations: port 1 and port 3 - the paired probe needed for
reciprocity ``S31 = S13``. fdtdx 0.6.2 returns NaN normalization for a mode
source travelling -x, so port 3 is excited by solving the x-mirrored scene
with a +x source at its port 1 and mapping detector names back; every source
in every run travels +x under the same normalization.

Wavelengths: 1.50, 1.525, 1.55, 1.575, 1.60 um, one FDTD run per wavelength per
excitation (fdtdx's S-parameter helper builds a single-wavelength scene).
"""

from __future__ import annotations

import time

import numpy as np

SPEC = {
    "spec_version": "carbon.exam-design.photonic-reference.v1",
    "fdtdx_version": "0.6.2",
    "n_si": 3.48,
    "n_sio2": 1.444,
    "wg_width_nm": 500,
    "wg_height_nm": 220,
    "bend_left_um": 3.0,
    "bend_right_um": 2.0,
    "port_pitch_um": 1.6,
    "lead_um": 1.0,
    "input_bounds": {"gap_nm": [150.0, 300.0], "length_um": [1.0, 6.0]},
    "wavelengths_um": [1.50, 1.525, 1.55, 1.575, 1.60],
    "resolution_nm": 30.0,
    "refined_resolution_nm": 20.0,
    "pml_layers": 10,
    "margin_y_um": 1.0,
    "margin_z_um": 0.9,
    "time_factor": 1.6,  # simulated time = factor x (group transit of the device + pulse)
}


def _centerline(
    x: np.ndarray,
    y_near: float,
    y_far: float,
    x0: float,
    bl: float,
    br: float,
    length: float,
):
    """Far (lead) -> cosine bend -> near (coupling) -> cosine bend -> far."""
    x1, x2, x3 = x0 + bl, x0 + bl + length, x0 + bl + length + br
    y = np.full_like(x, y_far)
    m = (x >= x0) & (x < x1)
    y[m] = y_far + (y_near - y_far) * 0.5 * (1 - np.cos(np.pi * (x[m] - x0) / bl))
    y[(x >= x1) & (x <= x2)] = y_near
    m = (x > x2) & (x <= x3)
    y[m] = y_near + (y_far - y_near) * 0.5 * (1 - np.cos(np.pi * (x[m] - x2) / br))
    return y


def straight_geometry(length_um: float) -> dict:
    """Calibration scene: one straight guide on the upper port line, no coupler.

    Transmission should be |S31|^2 ~ 1 with no partner guide to couple into, so
    it measures port normalization and discretization loss directly; and the
    scene is its own mirror image, so the mirrored-excitation mapping must return
    S13 = S31 to numerical precision. Neither check can be read off a coupler.
    """
    g = geometry(300.0, length_um)
    w = SPEC["wg_width_nm"] * 1e-9
    x = np.linspace(0, g["lx"], 4)
    top, bot = np.full_like(x, g["y_far"] + w / 2), np.full_like(x, g["y_far"] - w / 2)
    g["polys"] = [
        np.concatenate(
            [np.column_stack([x, top]), np.column_stack([x[::-1], bot[::-1]])]
        )
    ]
    return g


def geometry(gap_nm: float, length_um: float, mirror: bool = False) -> dict:
    um = 1e-6
    w = SPEC["wg_width_nm"] * 1e-9
    lead = SPEC["lead_um"] * um
    bl, br = SPEC["bend_left_um"] * um, SPEC["bend_right_um"] * um
    lx = 2 * lead + bl + br + length_um * um
    y_near = (gap_nm * 1e-9 + w) / 2
    y_far = SPEC["port_pitch_um"] * um / 2
    ly = 2 * y_far + w + 2 * SPEC["margin_y_um"] * um
    lz = SPEC["wg_height_nm"] * 1e-9 + 2 * SPEC["margin_z_um"] * um
    x = np.linspace(0, lx, 400)
    polys = []
    for sign in (+1, -1):
        yc = sign * _centerline(x, y_near, y_far, lead, bl, br, length_um * um)
        if mirror:
            yc = yc[::-1]
        top, bot = yc + w / 2, yc - w / 2
        verts = np.concatenate(
            [np.column_stack([x, top]), np.column_stack([x[::-1], bot[::-1]])]
        )
        polys.append(verts)
    return {"lx": lx, "ly": ly, "lz": lz, "y_far": y_far, "polys": polys}


def solve_case(
    case: dict, refined: bool = False, wavelengths=None, progress=None
) -> dict:
    import fdtdx
    import jax

    t0 = time.perf_counter()
    res = (
        case.get("resolution_nm")
        or (SPEC["refined_resolution_nm"] if refined else SPEC["resolution_nm"])
    ) * 1e-9
    if case.get("kind") == "straight":
        g = gm = straight_geometry(case["length_um"])
    else:
        g = geometry(case["gap_nm"], case["length_um"])
        gm = geometry(case["gap_nm"], case["length_um"], mirror=True)
    wls = wavelengths or SPEC["wavelengths_um"]
    mats = {
        "cladding": fdtdx.Material(permittivity=SPEC["n_sio2"] ** 2),
        "si": fdtdx.Material(permittivity=SPEC["n_si"] ** 2),
    }
    h = SPEC["wg_height_nm"] * 1e-9
    cz = g["lz"] / 2
    x_port = 0.4 * SPEC["lead_um"] * 1e-6
    pw, ph = 1.6e-6, 1.2e-6  # port cross-section around one guide
    y_up, y_dn = g["ly"] / 2 + g["y_far"], g["ly"] / 2 - g["y_far"]
    port = {
        "p1": (x_port, y_up),
        "p2": (x_port, y_dn),
        "p3": (g["lx"] - x_port, y_up),
        "p4": (g["lx"] - x_port, y_dn),
    }
    # Outgoing waves: +x at the right-hand ports, -x (reflection) at the left-hand ports.
    out_dir = {"p1": "-", "p2": "-", "p3": "+", "p4": "+"}
    # In the mirrored scene, original port p3 sits where p1 is, p4 where p2 is, and vice versa.
    mirror_name = {"p1": "p3", "p2": "p4", "p3": "p1", "p4": "p2"}
    n_g = 4.2
    t_sim = SPEC["time_factor"] * (g["lx"] * n_g / 299792458.0 + 120e-15)
    rec = {
        "case_id": case["case_id"],
        "inputs": {k: case[k] for k in ("gap_nm", "length_um", "kind") if k in case},
        "refined": refined,
        "resolution_nm": res * 1e9,
        "domain_um": [g["lx"] * 1e6, g["ly"] * 1e6, g["lz"] * 1e6],
        "cells": round(g["lx"] / res) * round(g["ly"] / res) * round(g["lz"] / res),
        "sim_time_fs": t_sim * 1e15,
        "runs": [],
    }
    S = {}
    try:
        for wl in wls:
            for src in ("p1", "p3"):
                geo = g if src == "p1" else gm
                polys = []
                for i, v in enumerate(geo["polys"]):
                    cx = 0.5 * (v[:, 0].min() + v[:, 0].max())
                    cy = 0.5 * (v[:, 1].min() + v[:, 1].max()) + g["ly"] / 2
                    vv = v - np.array([cx, 0.5 * (v[:, 1].min() + v[:, 1].max())])
                    poly = fdtdx.ExtrudedPolygon(
                        materials=mats,
                        material_name="si",
                        axis=2,
                        vertices=vv,
                        partial_real_shape=(None, None, h),
                        name=f"wg{i}",
                    )
                    polys.append((poly, (cx, cy, cz)))
                inp = [
                    fdtdx.PortSpec(
                        center=(*port["p1"], cz),
                        axis=0,
                        direction="+",
                        width=pw,
                        height=ph,
                        name="src",
                    )
                ]
                outs = [
                    fdtdx.PortSpec(
                        center=(*port[p], cz),
                        axis=0,
                        direction=out_dir[p],
                        width=pw,
                        height=ph,
                        name=f"d_{p}",
                    )
                    for p in ("p2", "p3", "p4")
                ]
                ts = time.perf_counter()
                objects, arrays, config = fdtdx.setup_sparams_simulation(
                    polygons=polys,
                    input_ports=inp,
                    output_ports=outs,
                    wavelength=wl * 1e-6,
                    resolution=res,
                    max_time=t_sim,
                    domain_size=(g["lx"], g["ly"], g["lz"]),
                    background_material=mats["cladding"],
                    pml_layers=SPEC["pml_layers"],
                )
                tset = time.perf_counter()
                sp, _ = fdtdx.calculate_sparam(
                    objects, arrays, config, input_port_name="src", show_progress=False
                )
                sp = {
                    k: complex(np.asarray(jax.device_get(v)).reshape(-1)[0])
                    for k, v in sp.items()
                }
                te = time.perf_counter()
                for (det, _src), val in sp.items():
                    if not det.startswith("d_"):
                        continue
                    local = det[2:]
                    name = local if src == "p1" else mirror_name[local]
                    S.setdefault(f"{name}<-{src}", {})[str(wl)] = [val.real, val.imag]
                rec["runs"].append(
                    {"wl_um": wl, "src": src, "setup_s": tset - ts, "run_s": te - tset}
                )
                if progress:
                    progress(rec)
    except Exception as e:  # noqa: BLE001 -- failure is typed
        msg = repr(e)
        # Toolchain/resource faults (GPU compiler, allocation) are infrastructure, never a reference failure.
        infra = any(
            k in msg
            for k in (
                "ptxas",
                "RESOURCE_EXHAUSTED",
                "CUDA_ERROR",
                "Could not open output file",
            )
        )
        rec.update(
            status="FAILED_INFRA" if infra else "REFERENCE_SOLVER_FAILED",
            error=msg[:400],
            wall_s=time.perf_counter() - t0,
            S=S,
        )
        return rec
    rec.update(status="OK", S=S, wall_s=time.perf_counter() - t0)
    try:
        import jax

        stats = jax.devices()[0].memory_stats() or {}
        rec["gpu_peak_bytes"] = stats.get("peak_bytes_in_use")
    except Exception:  # noqa: BLE001, S110 -- failure is typed
        pass
    return rec


def checks(S: dict, wls) -> dict:
    """Passivity and reciprocity residuals from one case's S entries (same normalization for both)."""
    out = {}
    for wl in map(str, wls):
        c = lambda k, wl=wl: (complex(*S[k][wl]) if k in S and wl in S[k] else None)
        col1 = [c(f"{p}<-p1") for p in ("p2", "p3", "p4")]
        col3 = [c(f"{p}<-p3") for p in ("p1", "p2", "p4")]
        out[wl] = {
            "sum_power_from_p1": float(sum(abs(v) ** 2 for v in col1 if v is not None)),
            "sum_power_from_p3": float(sum(abs(v) ** 2 for v in col3 if v is not None)),
            "reciprocity_31_13": (
                abs(c("p3<-p1") - c("p1<-p3"))
                if c("p3<-p1") is not None and c("p1<-p3") is not None
                else None
            ),
            "reciprocity_41_14": None,
        }
    return out

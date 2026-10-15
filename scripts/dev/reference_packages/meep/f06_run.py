"""Run one frozen f06 case inside the Meep 1.32.0 image.

    python3 f06_run.py case.json result.json

A case is ``{"schema": "carbon.f06.meep-case.v1", "decks": [...]}`` built by
``f06_deck.py``/``f06_freeze.py``. Decks run in order in one process; a
``normalization`` deck must precede the ``device`` decks of the same
cross-section and grid, which reuse its incident data (exact-key cache:
cross-section, grid, source, monitor and frequencies).

Observer (f06-meep.md sections 2-3, F06-SCIENCE-VALUES-01):

* incident power P_in = |alpha+|^2 of the TE0 mode in the normalization run
  at the back plane window (unit-power MPB mode coefficients);
* reflection = |alpha-|^2 / P_in from the device run's mode decomposition;
* reflected flux from scattered fields (device minus normalization DFT
  fields) through the full back face of a closed flux box;
* outward fluxes through the front, side, top and bottom faces of that box
  (non-overlapping faces, outward normals); material absorption is zero by
  the fixture's lossless law, so the residual is
  1 - R_flux - (front + sides + top + bottom) / P_in, never clipped;
* fibre coupling = |integral u*(cos(theta) Ey - Hx) dA|^2 / (4 P_t P_in) on
  the top face, with u the paraxial y-polarised Gaussian (Meep's exp(-i w t)
  convention: forward phase exp(+i k s)), P_t its analytic power. It is a
  subset of the top-face flux and is never added to it.
"""

from __future__ import annotations

import json
import math
import resource
import sys
import time

import meep as mp
import numpy as np

mp.verbosity(0)


def _v(dim, x, vert, y=0.0):
    return mp.Vector3(x, vert) if dim == 2 else mp.Vector3(x, y, vert)


class Frame:
    """Physical (x from cell left edge, z from Si top) -> Meep coordinates."""

    def __init__(self, dk):
        self.dk = dk
        self.dom = dk["domain"]
        self.dim = dk["dim"]

    def X(self, x):
        return x + self.dom["x_shift"]

    def Z(self, z):
        return z - self.dom["z_c"]

    def vec(self, x, z, y=0.0):
        return _v(self.dim, self.X(x), self.Z(z), y)

    def size(self, sx, sz, sy=0.0):
        return _v(self.dim, sx, sz, sy)


def media(dk):
    m = dk["materials"]
    return (
        mp.Medium(index=m["si"]),
        mp.Medium(index=m["sio2"]),
        mp.Medium(index=m["air"]),
    )


def geometry(dk, fr):
    si, sio2, air = media(dk)
    t_si, t_box = dk["stack"]["t_si_um"], dk["stack"]["t_box_um"]
    big = 1e3
    dim = dk["dim"]
    objs = [
        mp.Block(  # substrate
            center=fr.vec(0, -(t_si + t_box) - 50.0),
            size=fr.size(mp.inf, 100.0, mp.inf),
            material=si,
        ),
        mp.Block(center=fr.vec(0, -t_si - t_box / 2), size=fr.size(mp.inf, t_box, mp.inf), material=sio2),
    ]  # fmt: skip
    g = dk["geometry"]
    dom = dk["domain"]
    straight = dk["kind"] in ("normalization", "slab_mode")
    if dim == 2:
        objs.append(
            mp.Block(
                center=fr.vec(0, -t_si / 2), size=fr.size(mp.inf, t_si), material=si
            )
        )
    else:
        w0 = dk["guide"]["width_um"]
        x_end = dom["lx"] + big if straight else dom["x_t0"]
        objs.append(mp.Block(center=fr.vec((x_end - big) / 2, -t_si / 2),
                             size=fr.size(x_end + big, t_si, w0), material=si))  # fmt: skip
        if not straight:
            W = g["width_um"]
            x0, x1 = dom["x_t0"], dom["x_g0"]
            zc = fr.Z(-t_si)
            verts = [mp.Vector3(fr.X(x0), -w0 / 2, zc), mp.Vector3(fr.X(x1), -W / 2, zc),
                     mp.Vector3(fr.X(x1), W / 2, zc), mp.Vector3(fr.X(x0), w0 / 2, zc)]  # fmt: skip
            objs.append(
                mp.Prism(verts, height=t_si, axis=mp.Vector3(0, 0, 1), material=si)
            )
            objs.append(mp.Block(center=fr.vec(x1 + big / 2, -t_si / 2),
                                 size=fr.size(big, t_si, W), material=si))  # fmt: skip
    if not straight:
        p, duty, e = g["pitch_um"], g["duty"], g["etch_um"]
        trench = (1 - duty) * p
        lat = g["width_um"] + 0.4
        for i in range(g["periods"]):
            xs = dom["x_g0"] + i * p + duty * p
            objs.append(mp.Block(center=fr.vec(xs + trench / 2, (-e + 0.1) / 2),
                                 size=fr.size(trench, e + 0.1, lat), material=air))  # fmt: skip
    return objs


def mode_window(dk, fr, x):
    n = dk["numerics"]
    z0, z1 = n["mode_window_z_um"]
    hy = n["mode_window_y_um"]
    return fr.vec(x, (z0 + z1) / 2), fr.size(0, z1 - z0, 2 * hy)


def parity(dk):
    return mp.ODD_Y if dk["dim"] == 3 else mp.ODD_Z


def simulation(dk, fr, sources, extra_geometry=()):
    dom = dk["domain"]
    n = dk["numerics"]
    cell = fr.size(dom["lx"], dom["lz"], dom.get("ly", 0.0))
    sym = [mp.Mirror(mp.Y, phase=-1)] if dk["symmetry"] == "mirror_y_odd" else []
    return mp.Simulation(
        cell_size=cell,
        resolution=dom["resolution"],
        boundary_layers=[mp.PML(dom["pml_um"])],
        geometry=geometry(dk, fr) + list(extra_geometry),
        sources=sources,
        symmetries=sym,
        eps_averaging=n["eps_averaging"],
        subpixel_tol=n["subpixel_tol"],
        subpixel_maxeval=n["subpixel_maxeval"],
        Courant=n["courant"],
        default_material=mp.Medium(index=dk["materials"]["air"]),
        dimensions=dk["dim"],
    )


def eig_source(dk, fr, fcen):
    c, s = mode_window(dk, fr, dk["domain"]["x_src"])
    return [
        mp.EigenModeSource(
            mp.GaussianSource(fcen, fwidth=dk["numerics"]["fwidth"]),
            center=c,
            size=s,
            eig_band=1,
            eig_parity=parity(dk),
            eig_kpoint=mp.Vector3(1, 0, 0),
            eig_match_freq=True,
        )
    ]


def box_faces(dk, fr):
    """Closed flux box faces (Meep FluxRegions); outward-positive weights."""
    d = dk["domain"]
    xr, xf, zu, zd = d["x_r"], d["x_f"], d["z_up"], d["z_down"]
    zm, xm = (zu + zd) / 2, (xr + xf) / 2
    faces = {
        "back": mp.FluxRegion(center=fr.vec(xr, zm), size=fr.size(0, zu - zd, 2 * d.get("y_side", 0))),
        "front": mp.FluxRegion(center=fr.vec(xf, zm), size=fr.size(0, zu - zd, 2 * d.get("y_side", 0))),
        "top": mp.FluxRegion(center=fr.vec(xm, zu), size=fr.size(xf - xr, 0, 2 * d.get("y_side", 0))),
        "bottom": mp.FluxRegion(center=fr.vec(xm, zd), size=fr.size(xf - xr, 0, 2 * d.get("y_side", 0)), weight=-1),
    }  # fmt: skip
    if dk["dim"] == 3:
        ys = d["y_side"]
        faces["side_plus"] = mp.FluxRegion(
            center=fr.vec(xm, zm, ys), size=fr.size(xf - xr, zu - zd, 0)
        )
        faces["side_minus"] = mp.FluxRegion(center=fr.vec(xm, zm, -ys), size=fr.size(xf - xr, zu - zd, 0), weight=-1)  # fmt: skip
    return faces


def run_until(sim, dk, t_min):
    n = dk["numerics"]
    t0 = time.time()
    sim.run(
        until=mp.stop_when_dft_decayed(
            tol=n["dft_decay_tol"],
            minimum_run_time=t_min,
            maximum_run_time=t_min + n["max_run_after_sources"],
        )
    )
    return {
        "sim_time": sim.meep_time(),
        "timesteps": sim.timestep(),
        "wall_s": time.time() - t0,
    }


def source_end(dk):
    return 2 * 5.0 / dk["numerics"]["fwidth"]


def run_normalization(dk):
    fr = Frame(dk)
    freqs = dk["frequencies"]
    sim = simulation(dk, fr, eig_source(dk, fr, dk["fcen"]))
    back = box_faces(dk, fr)["back"]
    flux = sim.add_flux(freqs, back)
    c, s = mode_window(dk, fr, dk["domain"]["x_r"])
    mon = sim.add_mode_monitor(freqs, mp.ModeRegion(center=c, size=s))
    c2, s2 = mode_window(dk, fr, dk["domain"]["x_r"] + 0.6)
    mon2 = sim.add_mode_monitor(freqs, mp.ModeRegion(center=c2, size=s2))
    t_min = source_end(dk) + dk["numerics"]["min_run_after_sources"]
    timing = run_until(sim, dk, t_min)
    a1 = sim.get_eigenmode_coefficients(mon, [1], eig_parity=parity(dk))
    a2 = sim.get_eigenmode_coefficients(mon2, [1], eig_parity=parity(dk))
    fl = np.array(mp.get_fluxes(flux))
    cache = {
        "flux_data": sim.get_flux_data(flux),
        "alpha_plus": a1.alpha[0, :, 0].copy(),
    }
    p_in = np.abs(a1.alpha[0, :, 0]) ** 2
    rows = []
    for i, f in enumerate(freqs):
        rows.append({
            "wavelength_um": 1 / f,
            "p_in_mode": float(p_in[i]),
            "p_in_flux_back_face": float(fl[i]),
            "flux_parity": float(fl[i] / p_in[i] - 1),
            "te0_reflection_straight": float(abs(a1.alpha[0, i, 1]) ** 2 / p_in[i]),
            "te0_transmission_0p6um": float(abs(a2.alpha[0, i, 0]) ** 2 / p_in[i]),
            "alpha_plus": [float(a1.alpha[0, i, 0].real), float(a1.alpha[0, i, 0].imag)],
            "neff": float(a1.kdom[i].x / f) if a1.kdom else None,
        })  # fmt: skip
    info = {"kind": "normalization", "cells": dk["cells"], **timing, "rows": rows}
    sim.reset_meep()
    return info, cache


def gaussian_target(dk, fr, xs, ys, zplane, f, tgt):
    """Paraxial y-polarised Gaussian u on the top plane (physical coords)."""
    fib = dk["fibre"]
    th = math.radians(fib["tilt_deg_towards_plus_x"])
    w0 = fib["w0_um"]
    k = 2 * math.pi * f * dk["materials"]["air"]
    zr = k * w0**2 / 2
    xw = dk["domain"]["x_g0"] + tgt["waist_from_grating_start_um"]
    yw = tgt["dy_um"]
    zw = fib["waist_above_si_top_um"]
    X, Y = np.meshgrid(xs - dk["domain"]["x_shift"], ys, indexing="ij")
    rx, rz = X - xw, zplane - zw
    ry = (Y - yw) if dk["dim"] == 3 else 0.0 * X  # 2D: y is the invariant axis
    s = rx * math.sin(th) + rz * math.cos(th)
    rho2 = rx**2 + ry**2 + rz**2 - s**2
    q = s - 1j * zr
    if dk["dim"] == 3:
        u = (-1j * zr / q) * np.exp(1j * k * s + 1j * k * rho2 / (2 * q))
        p_t = math.pi * w0**2 / 2
    else:
        u = np.sqrt(-1j * zr / q) * np.exp(1j * k * s + 1j * k * rho2 / (2 * q))
        p_t = w0 * math.sqrt(math.pi / 2)
    return u, p_t, th


def plane_metadata(sim, dk, dft_obj):
    """Plane coordinates and cubature weights; 2D lines use y = [0]."""
    xs, ys, _zs, w = sim.get_array_metadata(dft_cell=dft_obj)
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float) if dk["dim"] == 3 else np.array([0.0])
    w = np.asarray(w, dtype=float).reshape(len(xs), len(ys))
    return xs, ys, w


def dft_arr(sim, dft_obj, component, index, w):
    a = np.asarray(sim.get_dft_array(dft_obj, component, index))
    if a.size != w.size:
        raise RuntimeError(
            f"DFT array {a.shape} does not match plane weights {w.shape}"
        )
    return a.reshape(w.shape)


def run_device(dk, cache):
    fr = Frame(dk)
    freqs = dk["frequencies"]
    sim = simulation(dk, fr, eig_source(dk, fr, dk["fcen"]))
    faces = box_faces(dk, fr)
    fluxes = {name: sim.add_flux(freqs, reg) for name, reg in faces.items()}
    sim.load_minus_flux_data(fluxes["back"], cache["flux_data"])
    # a second, unloaded back-face flux gives the device's net inflow
    net_back = sim.add_flux(freqs, faces["back"])
    c, s = mode_window(dk, fr, dk["domain"]["x_r"])
    mon = sim.add_mode_monitor(freqs, mp.ModeRegion(center=c, size=s))
    top = faces["top"]
    if dk["dim"] == 3:
        comps = [mp.Ex, mp.Ey, mp.Hx, mp.Hy]
    else:
        comps = [mp.Ez, mp.Hx]
    dft_top = sim.add_dft_fields(comps, freqs, center=top.center, size=top.size)
    d = dk["domain"]
    path = d["x_f"] - d["x_r"]
    n = dk["numerics"]
    t_min = (
        source_end(dk) + n["transit_group_index"] * path + n["min_run_after_sources"]
    )
    timing = run_until(sim, dk, t_min)
    alpha = sim.get_eigenmode_coefficients(mon, [1], eig_parity=parity(dk)).alpha
    flux = {name: np.array(mp.get_fluxes(fl)) for name, fl in fluxes.items()}
    net = np.array(mp.get_fluxes(net_back))
    xs, ys, w = plane_metadata(sim, dk, dft_top)
    rows = []
    for i, f in enumerate(freqs):
        p_in = abs(cache["alpha_plus"][i]) ** 2
        if dk["dim"] == 3:
            ex, ey, hx, hy = (dft_arr(sim, dft_top, cp, i, w) for cp in comps)
            sz_dens = np.real(np.conj(ex) * hy - np.conj(ey) * hx)
            e_t, h_t = ey, hx
        else:
            ez, hx = (dft_arr(sim, dft_top, cp, i, w) for cp in comps)
            # 2D: Meep y is vertical; (E x H*)_y = Ez Hx* -> Re(conj(Ez) Hx) sign below
            sz_dens = np.real(np.conj(ez) * hx)
            e_t, h_t = ez, hx
        top_from_fields = float(np.sum(w * sz_dens))
        out = {"R_flux": float(-flux["back"][i] / p_in)}
        for name in ("front", "top", "bottom", "side_plus", "side_minus"):
            if name in flux:
                out[name] = float(flux[name][i] / p_in)
        outward = sum(out[k] for k in out if k != "R_flux")
        row = {
            "wavelength_um": 1 / f,
            "p_in_mode": float(p_in),
            "alpha_plus_device": [float(alpha[0, i, 0].real), float(alpha[0, i, 0].imag)],
            "alpha_minus": [float(alpha[0, i, 1].real), float(alpha[0, i, 1].imag)],
            "reflection_te0": float(abs(alpha[0, i, 1]) ** 2 / p_in),
            "incident_amplitude_drift": float(abs(alpha[0, i, 0] - cache["alpha_plus"][i]) / abs(cache["alpha_plus"][i])),
            "net_inflow_back": float(net[i] / p_in),
            "top_from_fields": top_from_fields / p_in,
            "absorbed": 0.0,
            "residual": float(1 - out["R_flux"] - outward),
            **out,
            "coupling": {},
            "overlap": {},
        }  # fmt: skip
        zplane = d["z_up"]
        for tgt in dk["targets"]:
            u, p_t, th = gaussian_target(dk, fr, xs, ys, zplane, f, tgt)
            u = u.reshape(w.shape)
            if dk["dim"] == 3:
                num = np.sum(w * np.conj(u) * (math.cos(th) * e_t - h_t))
            else:
                # 2D frame (x, vert, z): target E = z u, H = (cos th, -sin th, 0) u;
                # (E x H_t* + E_t* x H)_vert = u* (cos th Ez + Hx)
                num = np.sum(w * np.conj(u) * (math.cos(th) * e_t + h_t))
            pc = abs(num) ** 2 / (4 * p_t)
            row["coupling"][str(tgt["vector"])] = float(pc / p_in)
            row["overlap"][str(tgt["vector"])] = [float(num.real), float(num.imag)]
        rows.append(row)
    info = {
        "kind": "device",
        "vectors": dk["vectors"],
        "cells": dk["cells"],
        **timing,
        "rows": rows,
    }
    sim.reset_meep()
    return info


def run_slab_mode(dk):
    """TE0 slab effective index from Meep/MPB at the deck grid (2D, Ez)."""
    fr = Frame(dk)
    sim = simulation(dk, fr, [])
    sim.init_sim()
    c, s = mode_window(dk, fr, dk["domain"]["x_r"])
    rows = []
    for f in dk["frequencies"]:
        em = sim.get_eigenmode(f, mp.X, mp.Volume(center=c, size=s), band_num=1,
                               kpoint=mp.Vector3(2.5 * f), parity=parity(dk))  # fmt: skip
        rows.append({"wavelength_um": 1 / f, "neff": float(em.k.x / f)})
    sim.reset_meep()
    return {"kind": "slab_mode", "rows": rows}


def run_gaussian_free(dk):
    """Free-space control: Meep Gaussian beam source vs the target overlap."""
    fr = Frame(dk)
    d = dk["domain"]
    f = dk["fcen"]
    tgt = dk["targets"][0]
    fib = dk["fibre"]
    th = math.radians(fib["tilt_deg_towards_plus_x"])
    z_src = d["z_down"] + 0.2
    x_src_c = (d["x_r"] + d["x_f"]) / 2
    xw = d["x_g0"] + tgt["waist_from_grating_start_um"]
    beam_x0 = _v(
        dk["dim"], xw - x_src_c, fib["waist_above_si_top_um"] - z_src, tgt["dy_um"]
    )
    kdir = _v(dk["dim"], math.sin(th), math.cos(th))
    size = fr.size(d["x_f"] - d["x_r"] + 2.0, 0, 2 * d.get("y_side", 0) + 2.0)
    cls = mp.GaussianBeam3DSource if dk["dim"] == 3 else mp.GaussianBeam2DSource
    pol = mp.Vector3(0, 1, 0) if dk["dim"] == 3 else mp.Vector3(0, 0, 1)
    src = cls(mp.GaussianSource(f, fwidth=dk["numerics"]["fwidth"]), center=fr.vec(x_src_c, z_src),
              size=size, beam_x0=beam_x0, beam_kdir=kdir, beam_w0=fib["w0_um"], beam_E0=pol)  # fmt: skip
    sim = mp.Simulation(
        cell_size=fr.size(d["lx"], d["lz"], d.get("ly", 0.0)),
        resolution=d["resolution"],
        boundary_layers=[mp.PML(d["pml_um"])],
        sources=[src],
        default_material=mp.Medium(index=1.0),
        dimensions=dk["dim"],
    )
    top = box_faces(dk, fr)["top"]
    flux = sim.add_flux([f], top)
    comps = [mp.Ex, mp.Ey, mp.Hx, mp.Hy] if dk["dim"] == 3 else [mp.Ez, mp.Hx]
    dft = sim.add_dft_fields(comps, [f], center=top.center, size=top.size)
    timing = run_until(
        sim, dk, source_end(dk) + dk["numerics"]["min_run_after_sources"]
    )
    xs, ys, w = plane_metadata(sim, dk, dft)
    u, p_t, th = gaussian_target(dk, fr, xs, ys, d["z_up"], f, tgt)
    u = u.reshape(w.shape)
    if dk["dim"] == 3:
        ex, ey, hx, hy = (dft_arr(sim, dft, cp, 0, w) for cp in comps)
        num = np.sum(w * np.conj(u) * (math.cos(th) * ey - hx))
        top_fields = float(np.sum(w * np.real(np.conj(ex) * hy - np.conj(ey) * hx)))
    else:
        ez, hx = (dft_arr(sim, dft, cp, 0, w) for cp in comps)
        num = np.sum(w * np.conj(u) * (math.cos(th) * ez + hx))
        top_fields = float(np.sum(w * np.real(np.conj(ez) * hx)))
    pc = abs(num) ** 2 / (4 * p_t)
    fl = float(mp.get_fluxes(flux)[0])
    sim.reset_meep()
    return {"kind": "gaussian_free", **timing, "top_flux": fl, "top_from_fields": top_fields,
            "overlap_power": float(pc), "overlap_fraction_of_flux": float(pc / fl)}  # fmt: skip


def main(case_path, out_path):
    with open(case_path) as fh:
        case = json.load(fh)
    t0 = time.time()
    results, cache = [], {}
    for dk in case["decks"]:
        key = json.dumps([dk["domain"].get("ly"), dk["domain"]["lz"], dk["domain"]["h_um"], dk["frequencies"], dk["fcen"], dk["symmetry"], dk["dim"], dk["domain"]["pml_um"], dk["domain"]["pad_scale"]])  # fmt: skip
        if dk["kind"] == "normalization":
            info, cache[key] = run_normalization(dk)
        elif dk["kind"] == "device":
            if key not in cache:
                raise SystemExit("device deck without a matching normalization deck")
            info = run_device(dk, cache[key])
        elif dk["kind"] == "slab_mode":
            info = run_slab_mode(dk)
        elif dk["kind"] == "gaussian_free":
            info = run_gaussian_free(dk)
        else:
            raise SystemExit(f"unknown deck kind {dk['kind']}")
        info["label"] = dk.get("extra", {}).get("label")
        results.append(info)
        print(json.dumps({k: info[k] for k in info if k != "rows"}), flush=True)
    ru = resource.getrusage(resource.RUSAGE_SELF)
    out = {
        "schema": "carbon.f06.meep-result.v1",
        "meep_version": mp.__version__,
        "case_schema": case.get("schema"),
        "results": results,
        "process": {
            "wall_s": time.time() - t0,
            "cpu_s": ru.ru_utime + ru.ru_stime,
            "maxrss_mib": ru.ru_maxrss / 1024,
        },
    }
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

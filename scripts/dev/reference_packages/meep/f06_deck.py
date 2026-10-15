"""f06 grating-coupler Meep decks: geometry, domain, monitors and memory forecast.

Pure standard library so the host can generate, freeze and forecast decks
without Meep. ``f06_run.py`` (inside the Meep image) builds the simulation
from a deck JSON and nothing else, so a deck's SHA-256 identifies the case.

Conventions (pinned here, F06-SCIENCE-VALUES-01 / f06-meep.md sections 2-3):

* Length unit um, Meep c = 1, frequency f = 1/lambda_um. The five exact
  wavelengths 1.530 ... 1.570 um are registered as their inverse frequencies.
* 3D Meep axes: x = guided propagation, y = lateral, z = vertical (z = 0 is
  the unetched Si top). 2D x/z adapter: Meep x = x, Meep y = physical z,
  physical y is the invariant direction and physical TE (E along y) is Meep Ez.
* Stack: Si 0.22 um on 2.0 um SiO2 BOX on semi-infinite Si substrate, air
  above; lossless nondispersive indices Si 3.48, SiO2 1.44, air 1.
* 500 nm input guide, 10 um linear taper from 0.5 um to the grating width,
  then N periods starting at the taper end, each an unetched tooth of length
  duty * pitch followed by an etched trench of depth etch; the full-thickness
  wide slab continues after the last period into the +x absorber.
* Fibre: Gaussian, MFD 10.4 um (w0 = 5.2 um), y-polarised (TE), waist 2.0 um
  above the Si top, axis tilted 10 deg from +z towards +x (the guided
  propagation direction), waist centre at (nominal grating centre + dx, dy).
  The fibre stays aligned to the *mask-intended* (nominal) grating centre
  when a fabrication vector perturbs pitch/etch/duty.
* Tolerance vectors are applied to the geometry before validation; an
  invalid perturbed geometry rejects the design (no clipping).
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

SCHEMA = "carbon.f06.meep-deck.v1"
WAVELENGTHS_UM = (1.530, 1.540, 1.550, 1.560, 1.570)
FREQUENCIES = tuple(1.0 / w for w in WAVELENGTHS_UM)
N_SI, N_SIO2, N_AIR = 3.48, 1.44, 1.0
T_SI, T_BOX = 0.22, 2.0
GUIDE_W, TAPER_L = 0.5, 10.0
MFD_UM, WAIST_Z_UM, TILT_DEG = 10.4, 2.0, 10.0
MIN_FEATURE_UM = 0.180
#: Packet vector order (pitch nm, etch nm, duty, dx um, dy um).
VECTORS = (
    (0, 0, 0.0, 0.0, 0.0),
    (-10, -10, -0.03, 0.0, 0.0),
    (10, 10, 0.03, 0.0, 0.0),
    (0, 0, 0.0, -1.0, 0.0),
    (0, 0, 0.0, 1.0, 0.0),
    (0, 0, 0.0, 0.0, -1.0),
    (0, 0, 0.0, 0.0, 1.0),
    (-10, 10, 0.03, -1.0, 1.0),
    (10, -10, -0.03, 1.0, -1.0),
)
GRAMMAR = {
    "periods": (12, 20),
    "pitch_nm": (580, 680),
    "duty": (0.35, 0.65),
    "etch_nm": (70, 130),
    "width_um": (8, 12),
}
#: Numerical settings registered by F06-SCIENCE-VALUES-01 (DEVELOPMENT).
NUMERICS = {
    "pml_um": 1.0,
    "pad_x_um": 1.0,  # grating end -> front flux plane
    "pad_y_um": 1.0,  # grating edge -> side flux plane
    "air_um": 0.5,  # Si top -> top flux / fibre-overlap plane
    "sub_um": 0.2,  # BOX bottom -> bottom flux plane (inside substrate)
    "gap_um": 0.3,  # flux plane -> absorber
    "src_from_pml_um": 0.3,
    "monitor_from_src_um": 0.4,
    "taper_from_monitor_um": 0.5,
    "grating_from_monitor_2d_um": 1.0,
    "mode_window_y_um": 1.5,  # half width
    "mode_window_z_um": (-1.5, 1.0),
    "courant": 0.5,
    "fwidth": 0.1,
    "dft_decay_tol": 1e-6,
    "min_run_after_sources": 50.0,
    "transit_group_index": 4.5,  # minimum run covers a guided transit of the box
    "max_run_after_sources": 2000.0,
    "eps_averaging": True,
    "subpixel_tol": 1e-4,
    "subpixel_maxeval": 100000,
}
ENGINE_COMMAND = "python3 /case/f06_run.py deck.json result.json > meep.log 2>&1"


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha256(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def design(periods, pitch_nm, duty, etch_nm, width_um, label=None):
    d = {
        "periods": int(periods),
        "pitch_nm": float(pitch_nm),
        "duty": float(duty),
        "etch_nm": float(etch_nm),
        "width_um": float(width_um),
    }
    if label:
        d["label"] = label
    return d


def in_grammar(d):
    for key, (lo, hi) in GRAMMAR.items():
        if not lo <= d[key] <= hi:
            return False
    return True


def perturbed(d, vector):
    dp, de, dd, _dx, _dy = VECTORS[vector]
    return {
        "periods": d["periods"],
        "pitch_um": (d["pitch_nm"] + dp) / 1000.0,
        "duty": d["duty"] + dd,
        "etch_um": (d["etch_nm"] + de) / 1000.0,
        "width_um": d["width_um"],
    }


def feature_check(g):
    tooth = g["duty"] * g["pitch_um"]
    trench = (1.0 - g["duty"]) * g["pitch_um"]
    problems = []
    if tooth < MIN_FEATURE_UM - 1e-12:
        problems.append(f"tooth {tooth * 1000:.1f} nm < 180 nm")
    if trench < MIN_FEATURE_UM - 1e-12:
        problems.append(f"trench {trench * 1000:.1f} nm < 180 nm")
    if not 0 < g["etch_um"] < T_SI:
        problems.append("residual Si thickness not positive")
    return problems


def valid(d):
    """All nine perturbed geometries must pass before the design exists."""
    if not in_grammar(d):
        return False
    return all(not feature_check(perturbed(d, v)) for v in range(len(VECTORS)))


def geometry_groups():
    """Vectors sharing one geometry (fibre offsets only change the target)."""
    groups = {}
    for i, (dp, de, dd, _dx, _dy) in enumerate(VECTORS):
        groups.setdefault((dp, de, dd), []).append(i)
    return list(groups.values())


def _snap(value, h):
    return math.ceil(value / h - 1e-9) * h


def _cells(n):
    return round(n)


def domain(d, dim, h, pml=None, pad_scale=1.0):
    """Grid-aligned cell and plane coordinates (um, Meep frame) for a design.

    The cell x origin is its left edge before centring, so the source, mode
    window and back flux plane sit at the same grid offset in every device and
    normalization run of the same cross-section and grid.
    """
    n = NUMERICS
    pml = n["pml_um"] if pml is None else pml
    pad = {k: n[k] * pad_scale for k in ("pad_x_um", "pad_y_um", "air_um", "sub_um")}
    x_src = pml + n["src_from_pml_um"]
    x_r = x_src + n["monitor_from_src_um"]
    if dim == 3:
        x_t0 = x_r + n["taper_from_monitor_um"]
        x_g0 = x_t0 + TAPER_L
    else:
        x_t0 = None
        x_g0 = x_r + n["grating_from_monitor_2d_um"]
    longest = d["periods"] * (d["pitch_nm"] + 10) / 1000.0
    x_f = x_g0 + longest + pad["pad_x_um"]
    lx = _snap(x_f + n["gap_um"] + pml, 2 * h)
    z_up = pad["air_um"]
    z_down = -(T_SI + T_BOX + pad["sub_um"])
    z_top = z_up + n["gap_um"] + pml
    z_bot = z_down - n["gap_um"] - pml
    # vertical cell: whole number of 2h, z = 0 kept on the grid
    k_bot = math.ceil(-z_bot / h - 1e-9)
    k_top = math.ceil(z_top / h - 1e-9)
    if (k_bot + k_top) % 2:
        k_top += 1
    z_lo, z_hi = -k_bot * h, k_top * h
    lz = z_hi - z_lo
    z_c = (z_hi + z_lo) / 2
    out = {
        "dim": dim,
        "h_um": h,
        "resolution": 1.0 / h,
        "pml_um": pml,
        "pad_scale": pad_scale,
        "x_shift": -lx / 2,  # physical x (left edge = 0) -> Meep x
        "x_src": x_src,
        "x_r": x_r,
        "x_t0": x_t0,
        "x_g0": x_g0,
        "x_f": x_f,
        "z_up": z_up,
        "z_down": z_down,
        "z_c": z_c,  # physical z -> Meep vertical = z - z_c
        "lx": lx,
        "lz": lz,
    }
    if dim == 3:
        y_side = d["width_um"] / 2 + pad["pad_y_um"]
        ly = _snap(2 * (y_side + n["gap_um"] + pml), 2 * h)
        out.update({"y_side": y_side, "ly": ly})
    return out


def normalization_domain(dom):
    """Short straight-guide domain with the device cross-section and offsets."""
    n = NUMERICS
    h = dom["h_um"]
    out = dict(dom)
    x_end = dom["x_r"] + 1.0 + n["gap_um"] + dom["pml_um"]
    out["lx"] = _snap(x_end, 2 * h)
    out["x_shift"] = -out["lx"] / 2
    out["x_t0"] = out["x_g0"] = None
    out["x_f"] = dom["x_r"] + 1.0
    return out


def cell_count(dom, symmetric=False):
    h = dom["h_um"]
    nx, nz = _cells(dom["lx"] / h), _cells(dom["lz"] / h)
    if dom["dim"] == 2:
        return nx * nz
    ny = _cells(dom["ly"] / h)
    return nx * (ny // 2 if symmetric else ny) * nz


def fibre_targets(d, vectors):
    """Fibre waist centres (physical frame) for the vectors of one geometry."""
    centre = d["periods"] * d["pitch_nm"] / 2000.0
    return [
        {
            "vector": v,
            "dx_um": VECTORS[v][3],
            "dy_um": VECTORS[v][4],
            "waist_from_grating_start_um": centre + VECTORS[v][3],
        }
        for v in vectors
    ]


def deck(
    d,
    dim,
    h,
    vectors=None,
    kind="device",
    frequencies=FREQUENCIES,
    fcen=None,
    pml=None,
    pad_scale=1.0,
    decay_tol=None,
    symmetric=True,
    extra=None,
):
    """A complete deck for one geometry (all vectors sharing it) or its normalization."""
    if vectors is None:
        vectors = geometry_groups()[0]
    groups = [g for g in geometry_groups() if vectors[0] in g]
    if not groups or not set(vectors) <= set(groups[0]):
        raise ValueError("vectors must share one geometry")
    if not valid(d):
        raise ValueError(f"invalid design: {d}")
    dom = domain(d, dim, h, pml=pml, pad_scale=pad_scale)
    if kind == "normalization":
        dom = normalization_domain(dom)
    n = dict(NUMERICS)
    if decay_tol is not None:
        n["dft_decay_tol"] = decay_tol
    freqs = [float(f) for f in frequencies]
    out = {
        "schema": SCHEMA,
        "kind": kind,
        "dim": dim,
        "design": d,
        "vectors": list(vectors),
        "geometry": perturbed(d, vectors[0]),
        "targets": fibre_targets(d, vectors)
        if kind in ("device", "gaussian_free")
        else [],
        "domain": dom,
        "numerics": n,
        "frequencies": freqs,
        "fcen": float(fcen if fcen is not None else sum(freqs) / len(freqs)),
        "materials": {"si": N_SI, "sio2": N_SIO2, "air": N_AIR},
        "stack": {"t_si_um": T_SI, "t_box_um": T_BOX},
        "guide": {"width_um": GUIDE_W, "taper_um": TAPER_L},
        "fibre": {
            "mfd_um": MFD_UM,
            "w0_um": MFD_UM / 2,
            "waist_above_si_top_um": WAIST_Z_UM,
            "tilt_deg_towards_plus_x": TILT_DEG,
            "polarisation": "y (TE)",
        },
        "symmetry": "mirror_y_odd" if (dim == 3 and symmetric) else "none",
        "cells": cell_count(dom, symmetric=(dim == 3 and symmetric)),
    }
    if extra:
        out["extra"] = extra
    return out


def timesteps(dk, run_time):
    return math.ceil(run_time / (dk["numerics"]["courant"] * dk["domain"]["h_um"]))


#: Measured memory model (filled from local measurements; see the evidence
#: file). Bytes per simulated cell for complete 3D device runs incl. PML,
#: averaging tensors, DFT planes and Python peak. None until measured.
MEASURED_BYTES_PER_CELL_3D = None


def memory_forecast(dk, bytes_per_cell=None):
    """Forecast peak bytes: cells x per-cell bytes + plane DFT arrays."""
    dom = dk["domain"]
    h = dom["h_um"]
    per_cell = bytes_per_cell or MEASURED_BYTES_PER_CELL_3D or 96
    cells = dk["cells"]
    nf = len(dk["frequencies"])
    if dk["dim"] == 3:
        plane_xy = _cells((dom["x_f"] - dom["x_r"]) / h) * _cells(2 * dom["y_side"] / h)
        plane_yz = _cells(2 * dom["y_side"] / h) * _cells(
            (dom["z_up"] - dom["z_down"]) / h
        )
        plane_xz = _cells((dom["x_f"] - dom["x_r"]) / h) * _cells(
            (dom["z_up"] - dom["z_down"]) / h
        )
        # flux planes: 4 tangential complex components; top plane also dft_fields
        planes = 2 * plane_xy + 2 * plane_yz + 2 * plane_xz + plane_xy
    else:
        planes = 3 * _cells((dom["x_f"] - dom["x_r"]) / h) + 2 * _cells(
            (dom["z_up"] - dom["z_down"]) / h
        )
    dft_bytes = planes * 4 * nf * 16
    return {
        "cells": cells,
        "bytes_per_cell": per_cell,
        "field_bytes": cells * per_cell,
        "dft_plane_points": planes,
        "dft_bytes": dft_bytes,
        "total_gib": (cells * per_cell + dft_bytes) / 2**30,
    }


def write_case(dk, out_dir, run_script):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "deck.json").write_text(json.dumps(dk, indent=1, sort_keys=True) + "\n")
    (out_dir / "f06_run.py").write_bytes(Path(run_script).read_bytes())
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out_dir.iterdir())
        if p.is_file()
    }

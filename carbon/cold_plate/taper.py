"""DRAFT (exam-cooling, 21 Nov 2026; owner lock "Cooling tapered push", PATH_LOCK_20261120 LOCK UPDATE): Cooling's
TAPERED-channel design variant (intended path carbon/cold_plate/taper.py). WRAP, not edit: domain.py, openfoam.py,
mesh_family.py and analysis*.py stay byte-unchanged, so every existing version's bytes and records are untouched.

The variant: the channel width changes LINEARLY along the flow, from `channel_width_mm` at the inlet (x = 0) to
`channel_width_mm * taper` at the outlet (x = L), with the PERIOD (channel + fin) held constant, so the fin takes the
rest (`fin_out = period - w_out`). The reference stays the same periodic cell (half channel + half fin between symmetry
planes), the same solver, BCs, heat map and reads; only the outlet-end y vertices of the blockMesh move. taper = 1 is the
straight channel and reproduces `openfoam.files` byte for byte (checked by the selftest).

Inputs: the 9 of `domain.INPUTS` + `taper`. The inlet width/fin keep their public box; `taper` and the outlet fin floor are
HUMAN_INPUT until the owner/v2 rule them (Step 0 probe only uses public draws inside `TAPER_BOUNDS_PROPOSED`).
Reads that assume one width: analysis's Re-at-outlet check uses the INLET width; `files` records the outlet width and
`outlet_re_check` recomputes that check at the outlet geometry (a diagnostic; the reference's own checks are unchanged).
"""

from __future__ import annotations

import math

from . import domain, openfoam
from . import mesh_family as _mf

TAPER = "taper"
INPUTS = domain.INPUTS + (TAPER,)
#: PROPOSED for the Step 0 probe only (exam-cooling 03:0xZ plan): converging 0.5-0.8 and diverging 1.25-2.0 around 1.
#: NOT registered values: the version's taper bounds and the fin floor are HUMAN_INPUT (owner / v2 rule them).
TAPER_BOUNDS_PROPOSED = (0.5, 2.0)
FIN_OUT_MIN_MM_PROPOSED = 0.1


def split(case):
    """(the 9 straight inputs checked against the public box, taper, outlet width mm, outlet fin mm); refuses a taper
    outside the proposed bounds or an outlet fin below the floor."""
    if set(case) != set(INPUTS):
        raise ValueError("inputs must be exactly " + ", ".join(INPUTS))
    base = domain.check_inputs({k: case[k] for k in domain.INPUTS})
    t = case[TAPER]
    if type(t) not in (int, float) or not math.isfinite(t):
        raise ValueError("taper must be a finite number")
    lo, hi = TAPER_BOUNDS_PROPOSED
    if not lo <= t <= hi:
        raise ValueError(f"taper={t} is outside [{lo}, {hi}]")
    period = base["channel_width_mm"] + base["fin_width_mm"]
    w_out = base["channel_width_mm"] * float(t)
    fin_out = period - w_out
    if fin_out < FIN_OUT_MIN_MM_PROPOSED:
        raise ValueError(
            f"outlet fin {fin_out:.4g} mm is below {FIN_OUT_MIN_MM_PROPOSED} mm"
        )
    return base, float(t), w_out, fin_out


def _taper_mesh_text(text, length_mm, half_in, half_out):
    """The blockMeshDict text with every x = L vertex at the inlet channel half-width moved to the outlet half-width.

    Pure text transform (rev 4, v2 pre-read condition 1): no module global is swapped, so concurrent callers are safe. The
    blockMesh blocks have vertices only at x = 0 and x = L (selftest), so blockMesh's own linear interpolation between them
    makes the channel wall a straight line in x, i.e. an exactly linear taper (v2 condition 2).
    """
    out, in_vertices = [], False
    for line in text.split("\n"):
        s = line.strip()
        if s == "vertices (":
            in_vertices = True
        elif in_vertices and s == ");":
            in_vertices = False
        elif in_vertices and s.startswith("("):
            x, y, z = (float(v) for v in s.strip("()").split())
            if x == length_mm and math.isclose(
                y, half_in, rel_tol=0, abs_tol=1e-6
            ):  # 6 significant digits
                line = f"    ({x:.6g} {half_out:.6g} {z:.6g})"
        out.append(line)
    return "\n".join(out)


def files(case, *, mesh_family=None, **options):
    """Every file of the tapered case and its record (taper + outlet geometry added)."""
    base, t, w_out, fin_out = split(case)
    if mesh_family is None:
        texts, record = openfoam.files(base, **options)
    else:
        texts, record = _mf.files(base, mesh_family=mesh_family, **options)
    if w_out != base["channel_width_mm"]:
        texts = dict(texts)
        texts["system/blockMeshDict"] = _taper_mesh_text(
            texts["system/blockMeshDict"],
            domain.FIXED["footprint_mm"],
            base["channel_width_mm"] / 2,
            w_out / 2,
        )
    record = dict(record, taper=t, channel_width_out_mm=w_out, fin_width_out_mm=fin_out)
    return texts, record


def write_case(case, out, *, mesh_family=None, **options):
    """mesh_family.write_case for the tapered variant."""
    from pathlib import Path

    out = Path(out)
    if out.exists():
        raise FileExistsError(f"{out} exists; refusing to overwrite")
    texts, record = files(case, mesh_family=mesh_family, **options)
    for relative, text in texts.items():
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    out.chmod(0o700)
    return record


def outlet_re_check(case, m_out_half_kg_s, mu_out):
    """analysis.py's Re-at-outlet with the OUTLET width (the reference's own check uses the inlet width)."""
    base, _t, w_out, _f = split(case)
    depth = base["channel_depth_mm"]
    face = w_out / 2 * depth * 1e-6
    d_h = 2 * w_out * depth / (w_out + depth) * 1e-3
    return m_out_half_kg_s / face * d_h / mu_out

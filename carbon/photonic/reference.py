"""The photonic coupler's reference service: tabulated supermodes, integrated.

The symmetric coupler's response depends on the cross-section only through
the even and odd supermode indices as functions of the gap and wavelength
(`carbon.photonic.coupler`). Those are computed once, on a gap ladder, by
`scripts/dev/photonic/build_tables.py`, and committed with their provenance
(`tables_v1.json`). A case's reference is then deterministic arithmetic:
interpolate the indices along the case's gap profile and integrate.

Outputs per wavelength (`domain`):
- `cross_power` = sin^2(dphi/2), the power reaching the cross port;
- `common_phase_rad` = (phi_even + phi_odd)/2, unwrapped: continuous in the
  inputs, unlike a wrapped phase.
S31 = e^{-i common} cos(dphi/2) and S41 = -i e^{-i common} sin(dphi/2) follow
exactly (`s_parameters`). The model is the declared local-supermode
contract, never the 3D FDTD (#345).
"""

from __future__ import annotations

import bisect
import cmath
import json
import math
from pathlib import Path

from .domain import (
    BEND_LEFT_UM,
    BEND_RIGHT_UM,
    PORT_PITCH_UM,
    WAVELENGTHS_UM,
    WIDTH_UM,
    check_inputs,
)

TABLES = Path(__file__).with_name("tables_v1.json")
TABLE_SCHEMA = "carbon.photonic.supermode-tables.v1"
Z_POINTS = 6000


def load_tables(path=TABLES):
    doc = json.loads(Path(path).read_text())
    if doc.get("schema") != TABLE_SCHEMA:
        raise ValueError(f"unsupported table schema {doc.get('schema')!r}")
    return doc


def _interp(xs, ys, x):
    """Piecewise-linear interpolation on increasing xs, clamped at the ends."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect.bisect_right(xs, x) - 1
    t = (x - xs[i]) / (xs[i + 1] - xs[i])
    return ys[i] + t * (ys[i + 1] - ys[i])


def gap_profile(z_um, gap_um, length_um):
    """Edge-to-edge gap at z from the left reference plane (cosine bends)."""
    near, far = gap_um, PORT_PITCH_UM - WIDTH_UM
    if z_um < BEND_LEFT_UM:
        return far + (near - far) * 0.5 * (1 - math.cos(math.pi * z_um / BEND_LEFT_UM))
    if z_um <= BEND_LEFT_UM + length_um:
        return near
    zr = z_um - BEND_LEFT_UM - length_um
    return near + (far - near) * 0.5 * (1 - math.cos(math.pi * zr / BEND_RIGHT_UM))


def evaluate(case, tables=None):
    """The reference outputs for one case's inputs, from the committed tables."""
    tables = tables or load_tables()
    if tables.get("status") != "OK":
        raise ValueError("the tables failed their reference checks")
    return integrate(case, tables["gaps_um"], tables["wavelengths"])


def integrate(case, gaps, rows, z_points=Z_POINTS):
    """Outputs from supermode indices tabulated at `gaps`: `rows` maps each
    wavelength's repr to its "n_even" and "n_odd" lists. The closed-form
    baseline (`analytic`) integrates its own indices the same way."""
    case = check_inputs(case)
    gap_um, length_um = case["gap_nm"] * 1e-3, case["length_um"]
    total = BEND_LEFT_UM + length_um + BEND_RIGHT_UM
    dz = total / z_points
    profile = [gap_profile((i + 0.5) * dz, gap_um, length_um) for i in range(z_points)]
    if min(profile) < gaps[0] - 1e-12 or max(profile) > gaps[-1] + 1e-12:
        raise ValueError("the case's gap profile leaves the tabulated range")
    cross, common = [], []
    for wl in WAVELENGTHS_UM:
        row = rows[repr(wl)]
        # The splitting decays almost exponentially with the gap: interpolate
        # its logarithm; the mean, linearly.
        log_split = [math.log(e - o) for e, o in zip(row["n_even"], row["n_odd"])]
        mean = [(e + o) / 2 for e, o in zip(row["n_even"], row["n_odd"])]
        k0 = 2 * math.pi / wl
        dphi = k0 * dz * sum(math.exp(_interp(gaps, log_split, g)) for g in profile)
        sigma = k0 * dz * sum(_interp(gaps, mean, g) for g in profile)
        cross.append(math.sin(dphi / 2) ** 2)
        common.append(sigma)
    return {"cross_power": cross, "common_phase_rad": common}


def s_parameters(outputs):
    """S31 and S41 per wavelength from the outputs, under the port convention."""
    result = []
    for power, sigma in zip(outputs["cross_power"], outputs["common_phase_rad"]):
        half = math.asin(math.sqrt(min(max(power, 0.0), 1.0)))
        phase = cmath.exp(-1j * sigma)
        result.append((phase * math.cos(half), -1j * phase * math.sin(half)))
    return result

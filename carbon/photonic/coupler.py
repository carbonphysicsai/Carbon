# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""A symmetric silicon directional coupler by local supermodes (#345).

**The model, declared.** Two identical silicon strips (width w, height h) in
silica, coupled over a straight section of length L at edge-to-edge gap g,
with cosine S-bends (left `BEND_LEFT_UM`, right `BEND_RIGHT_UM`) separating
them to `PORT_PITCH_UM` centre to centre at the ports: the geometry family of
the exam-design campaign's 3D FDTD reference (`scripts/dev/exam_design/
photonic_reference.py` SPEC), without its leads.

The light is described, at every z, by the two TE-like supermodes of the local
cross-section (even and odd, from `carbon.photonic.modes`). The structure is
mirror-symmetric about the plane between the guides, so the two supermodes do
not exchange power anywhere: each keeps its amplitude and accumulates the
phase k0 * integral of n_eff(separation(z)) dz. Radiation, reflection, bend
loss and power carried by higher-order modes are outside the model.

**Ports and phase, defined by construction (#345 tasks 1-2).** Each port's
mode is the TE0 mode of its guide alone, at the port separation:
- normalized to unit power, 1/2 integral of Re(E x H*) . z = 1;
- its sign fixed so the integral of Ex over its own core is real and
  positive.
S_out,in = sum over supermodes m of <m, out> exp(-i phi_m) <in, m>, with
<a, b> the power overlap. A supermode's own phase enters once conjugated and
once not, so it cancels: the S-parameters depend only on the port
convention, and the convention does not depend on the mesh or wavelength.
That is the repair of the campaign's relative-phase flips (RESULT section 9).

**Reference planes:** the start of the left bend and the end of the right
bend; z runs along the device axis, and phases accumulate along z (paraxial;
the guides' tilt in the bends is outside the model).

This is a new, explicit reference contract. It is not the planned 3D FDTD
reference and is never relabelled as one (#345).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import modes

N_SI, N_OX = 3.48, 1.444
HEIGHT_UM = 0.22
BEND_LEFT_UM, BEND_RIGHT_UM = 3.0, 2.0
PORT_PITCH_UM = 1.6
WAVELENGTHS_UM = (1.50, 1.525, 1.55, 1.575, 1.60)
MARGIN_X_UM, MARGIN_Y_UM = 1.0, 0.8


@dataclass(frozen=True)
class Grid:
    step_um: float
    z_points: int = 4000
    separations: int = 14


def _fraction(centres, step, lo, hi):
    """Fraction of each cell [c - step/2, c + step/2] inside [lo, hi]."""
    left = np.maximum(centres - step / 2, lo)
    right = np.minimum(centres + step / 2, hi)
    return np.clip(right - left, 0.0, None) / step


def _eps(nx, ny, step, cores):
    """Permittivity on the doubled grid with sub-pixel averaging.

    Each Yee component is averaged over its own cell the way its field meets
    the core's axis-aligned edges: harmonically across an edge it is normal
    to, arithmetically along an edge it is tangential to. So eps_xx (Ex,
    normal to the vertical edges) is harmonic in x then arithmetic in y,
    eps_yy the reverse, and eps_zz (tangential to every edge) arithmetic.
    The cores' true edges then enter every mesh, not the nearest grid line:
    rung P2 found the supermode splitting, exponential in the gap, erratic
    across meshes without this (0.0025, 0.0065, 0.0012 at a 500 nm gap)."""
    e_co, e_cl = N_SI**2, N_OX**2
    xs = np.arange(2 * nx) * 0.5 * step - nx * step / 2
    ys = np.arange(2 * ny) * 0.5 * step - ny * step / 2
    eps = np.full((2 * nx, 2 * ny), e_cl)
    fy = _fraction(ys, step, -HEIGHT_UM / 2, HEIGHT_UM / 2)
    for x0, x1 in cores:
        fx = _fraction(xs, step, x0, x1)
        big_fx, big_fy = np.meshgrid(fx, fy, indexing="ij")
        touched = (big_fx > 0) & (big_fy > 0)
        line_x = 1.0 / (big_fx / e_co + (1 - big_fx) / e_cl)
        line_y = 1.0 / (big_fy / e_co + (1 - big_fy) / e_cl)
        xx = big_fy * line_x + (1 - big_fy) * e_cl
        yy = big_fx * line_y + (1 - big_fx) * e_cl
        zz = e_cl + (e_co - e_cl) * big_fx * big_fy
        # Ex at [1::2, 0::2], Ey at [0::2, 1::2], Ez at [0::2, 0::2].
        part = np.full_like(eps, e_cl)
        part[1::2, 0::2] = xx[1::2, 0::2]
        part[0::2, 1::2] = yy[0::2, 1::2]
        part[0::2, 0::2] = zz[0::2, 0::2]
        eps = np.where(touched, np.maximum(eps, part), eps)
    return eps


def _shape(half_width_um, step):
    """Grid cells for a cross-section spanning +-half_width_um in x."""
    nx = math.ceil(2 * (half_width_um + MARGIN_X_UM) / step)
    ny = math.ceil((HEIGHT_UM + 2 * MARGIN_Y_UM) / step)
    return nx + nx % 2, ny + ny % 2


def _core_mask(nx, ny, step, x0, x1):
    """Ex positions (i+1/2, j) inside the core [x0, x1] x [-h/2, h/2]."""
    x = (np.arange(nx) + 0.5) * step - nx * step / 2
    y = np.arange(ny) * step - ny * step / 2
    big_x, big_y = np.meshgrid(x, y, indexing="ij")
    return (big_x >= x0) & (big_x <= x1) & (np.abs(big_y) <= HEIGHT_UM / 2)


def cross_section(width_um, separation_um, step, nx=None):
    """The pair's averaged permittivity on the doubled grid, and the grid's
    (nx, ny): sized for the pair, or for `nx` cells (the port grid) if given."""
    half = separation_um / 2 + width_um / 2
    if nx is None:
        nx, ny = _shape(half, step)
    else:
        ny = _shape(half, step)[1]
    cores = [
        (separation_um / 2 - width_um / 2, separation_um / 2 + width_um / 2),
        (-separation_um / 2 - width_um / 2, -separation_um / 2 + width_um / 2),
    ]
    return _eps(nx, ny, step, cores), (nx, ny)


def parity(mode):
    """The mode's Ex mirror parity about x = 0: +1 even, -1 odd; a magnitude
    below 1 measures how far it is from either."""
    ex = mode.ex
    return float(np.sum(ex * ex[::-1, :]).real / np.sum(abs(ex) ** 2))


def supermodes(width_um, separation_um, wavelength_um, step, nx=None):
    """(even, odd) TE-like supermodes of the pair at a centre separation,
    unit power, on a grid sized for `nx` cells (the port grid) if given."""
    eps, (nx, ny) = cross_section(width_um, separation_um, step, nx)
    # 2.65 sits above the TE0 of every strip in the range (2.506 for 500 nm,
    # rung P1), so the shift-invert search finds the even mode first.
    found = modes.solve(eps, step, step, wavelength_um, 6, 2.65)
    te = [m for m in found if m.te_fraction > 0.5][:2]
    if len(te) < 2:
        raise ValueError("fewer than two TE-like supermodes found")
    out = {}
    for mode in te:
        out["even" if parity(mode) > 0 else "odd"] = mode
    if set(out) != {"even", "odd"}:
        raise ValueError(f"supermodes not one even and one odd: {sorted(out)}")
    return out["even"], out["odd"], (nx, ny)


def port_modes(width_um, wavelength_um, step):
    """The upper and lower ports' TE0 modes, alone, at the port pitch, on the
    port-pitch grid; normalized and signed (see the module docstring)."""
    half = PORT_PITCH_UM / 2 + width_um / 2
    nx, ny = _shape(half, step)
    result = []
    for centre in (PORT_PITCH_UM / 2, -PORT_PITCH_UM / 2):
        x0, x1 = centre - width_um / 2, centre + width_um / 2
        eps = _eps(nx, ny, step, [(x0, x1)])
        found = modes.solve(eps, step, step, wavelength_um, 4, 2.6)
        te0 = next(m for m in found if m.te_fraction > 0.5)
        mask = _core_mask(nx, ny, step, x0, x1)
        result.append(modes.normalized(te0, step, step, mask))
    return result, (nx, ny)


def separation(z, width_um, gap_um, length_um):
    """Centre-to-centre separation at z (um) from the left reference plane."""
    near, far = width_um + gap_um, PORT_PITCH_UM
    bl, br = BEND_LEFT_UM, BEND_RIGHT_UM
    z = np.asarray(z, dtype=float)
    s = np.full_like(z, near)
    left = z < bl
    s[left] = far + (near - far) * 0.5 * (1 - np.cos(np.pi * z[left] / bl))
    right = z > bl + length_um
    zr = z[right] - bl - length_um
    s[right] = near + (far - near) * 0.5 * (1 - np.cos(np.pi * zr / br))
    return s


def solve_case(width_um, gap_um, length_um, grid, wavelengths=WAVELENGTHS_UM):
    """S31 (through) and S41 (cross) for input at port 1, per wavelength, with
    diagnostics. Lengths in um."""
    total = BEND_LEFT_UM + length_um + BEND_RIGHT_UM
    z = (np.arange(grid.z_points) + 0.5) * total / grid.z_points
    dz = total / grid.z_points
    s_z = separation(z, width_um, gap_um, length_um)
    # Separation ladder: geometric in the gap, from the coupling gap out to the
    # port pitch, where the supermodes no longer change.
    gaps = np.geomspace(gap_um, PORT_PITCH_UM - width_um, grid.separations)
    s_ladder = width_um + gaps
    results = {}
    for wl in wavelengths:
        k0 = 2 * np.pi / wl
        (port_up, port_low), shape = port_modes(width_um, wl, grid.step_um)
        n_even, n_odd = [], []
        for s in s_ladder:
            even, odd, _ = supermodes(width_um, s, wl, grid.step_um)
            n_even.append(even.n_eff)
            n_odd.append(odd.n_eff)
        n_even, n_odd = np.array(n_even), np.array(n_odd)
        # n_even - n_odd decays nearly exponentially with the gap; interpolate
        # its logarithm, and the mean linearly, both in the gap.
        log_split = np.log(n_even - n_odd)
        mean = (n_even + n_odd) / 2
        g_z = s_z - width_um
        split_z = np.exp(np.interp(g_z, gaps, log_split))
        mean_z = np.interp(g_z, gaps, mean)
        phi_even = k0 * np.sum(mean_z + split_z / 2) * dz
        phi_odd = k0 * np.sum(mean_z - split_z / 2) * dz
        # At the port pitch the two supermodes are degenerate to solver
        # precision (rung P2: at 20 nm the eigensolver returned
        # guide-localized combinations), so they are not projected
        # numerically. For an exactly mirror-symmetric pair they are
        # (upper + lower)/sqrt(2) and (upper - lower)/sqrt(2) in the limit
        # of separated guides, with the ports' sign rule, so:
        #   S31 = (e^{-i phi_e} + e^{-i phi_o}) / 2,
        #   S41 = (e^{-i phi_e} - e^{-i phi_o}) / 2,
        # and arg(S41 / S31) = -pi/2 exactly, at every mesh and wavelength.
        s31 = (np.exp(-1j * phi_even) + np.exp(-1j * phi_odd)) / 2
        s41 = (np.exp(-1j * phi_even) - np.exp(-1j * phi_odd)) / 2
        results[wl] = {
            "s31": complex(s31),
            "s41": complex(s41),
            "n_split_min_gap": float(n_even[0] - n_odd[0]),
            "n_mean_min_gap": float(mean[0]),
            "phase_difference_rad": float(phi_even - phi_odd),
            "phase_common_rad": float((phi_even + phi_odd) / 2),
            "port_n_eff": float(port_up.n_eff),
            "port_power_check": float(
                abs(modes.power_overlap(port_up, port_up, grid.step_um, grid.step_um))
            ),
            "port_cross_overlap": float(
                abs(modes.power_overlap(port_up, port_low, grid.step_um, grid.step_um))
            ),
            "shape": list(shape),
        }
    return results

# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""The photonic coupler's closed-form baseline: the effective index method.

The textbook two-step reduction of the strip pair (e.g. Okamoto,
"Fundamentals of Optical Waveguides", 2nd ed., sections 2.2 and 4.3):
1. the 220 nm silicon layer as a symmetric slab in silica; its TE0 index
   n_v is the core index of
2. a symmetric five-layer slab across the pair (silica, n_v core, silica
   gap, n_v core, silica), whose even and odd TM0 supermodes stand for the
   strips' (Ex dominant, normal to the vertical edges, hence TM here).
Both dispersion relations are closed-form and solved by bisection. The
supermode indices are then integrated along the gap profile exactly as the
reference integrates its tables (`reference.integrate`), so the baseline
differs from the reference only in where its indices come from.

Pure Python, no fitting, no reference data: the closed-form baseline the
readiness record needs. The method is known to overestimate a strip's index
(it treats the lateral confinement as a uniform slab), which the pilot
measures.
"""

from __future__ import annotations

import math

from .domain import HEIGHT_UM, N_OX, N_SI, WAVELENGTHS_UM, WIDTH_UM, ladder
from .reference import integrate

SCAN_POINTS = 4000


def _bisect(f, lo, hi, iterations=200):
    flo = f(lo)
    for _ in range(iterations):
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def slab_te0(n_core, n_clad, thickness_um, wavelength_um):
    """TE0 index of a symmetric slab: kappa tan(kappa d / 2) = gamma."""
    k0 = 2 * math.pi / wavelength_um
    half = thickness_um / 2

    def f(n):
        kappa = k0 * math.sqrt(n_core**2 - n**2)
        gamma = k0 * math.sqrt(n**2 - n_clad**2)
        return kappa * math.tan(kappa * half) - gamma

    # The fundamental branch has kappa d / 2 in [0, pi / 2).
    cutoff = n_core**2 - (math.pi / 2 / (k0 * half)) ** 2
    lo = max(n_clad, math.sqrt(cutoff) if cutoff > 0 else n_clad) * (1 + 1e-12)
    return _bisect(f, lo, n_core * (1 - 1e-12))


def pair_tm(n_core, n_clad, width_um, gap_um, wavelength_um, parity):
    """The highest TM index of the given parity ("even" or "odd") of two
    identical slabs of index n_core, width w, a gap g apart, in n_clad.

    Hy is cosh (even) or sinh (odd) in the gap, harmonic in a core and
    decaying outside; Hy and Hy'/n^2 are continuous. With the gap solution
    scaled by cosh(gamma g / 2), the outer boundary condition is g(n) = 0."""
    k0 = 2 * math.pi / wavelength_um
    ratio = n_core**2 / n_clad**2

    def g(n):
        kappa = k0 * math.sqrt(n_core**2 - n**2)
        gamma = k0 * math.sqrt(n**2 - n_clad**2)
        t = math.tanh(gamma * gap_um / 2)
        a, b = (
            (1.0, ratio * gamma * t / kappa)
            if parity == "even"
            else (
                t,
                ratio * gamma / kappa,
            )
        )
        c, s = math.cos(kappa * width_um), math.sin(kappa * width_um)
        return (kappa / n_core**2) * (-a * s + b * c) + (gamma / n_clad**2) * (
            a * c + b * s
        )

    top, bottom = n_core * (1 - 1e-9), n_clad * (1 + 1e-9)
    step = (top - bottom) / SCAN_POINTS
    previous_n, previous = top, g(top)
    for i in range(1, SCAN_POINTS + 1):
        n = top - i * step
        value = g(n)
        if (value > 0) != (previous > 0):
            return _bisect(g, n, previous_n)
        previous_n, previous = n, value
    raise ValueError(f"no {parity} TM mode found")


def indices(gap_um, wavelength_um):
    """(n_even, n_odd) of the pair by the effective index method."""
    n_v = slab_te0(N_SI, N_OX, HEIGHT_UM, wavelength_um)
    return tuple(
        pair_tm(n_v, N_OX, WIDTH_UM, gap_um, wavelength_um, p) for p in ("even", "odd")
    )


def tables():
    """The method's indices on the reference's gap ladder."""
    gaps = ladder()
    rows = {}
    for wl in WAVELENGTHS_UM:
        pairs = [indices(g, wl) for g in gaps]
        rows[repr(wl)] = {
            "n_even": [e for e, _ in pairs],
            "n_odd": [o for _, o in pairs],
        }
    return gaps, rows


_TABLES = None


def predict(case):
    """The baseline's outputs for one case's inputs."""
    global _TABLES
    if _TABLES is None:
        _TABLES = tables()
    return integrate(case, *_TABLES)

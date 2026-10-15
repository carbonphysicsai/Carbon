"""f17 analytic and independent controls for the OpenFOAM v2506 route.

Smooth 300 x 100 um x 10 mm duct (blockMesh only, the grooved deck's patch
names, inlet split at y = 150 um):

    poiseuille   developed-segment pressure gradient (2-8 mm) against the
                 exact rectangular-duct series, at h = 10 and 7.071 um
    uniform      both inlets c = 1: outlet and field must stay c = 1
    split        c = 0 / 1: outlet flux-weighted M against an independent
                 cross-section marching solution (fully developed series
                 velocity, Crank-Nicolson in x), lowest- and highest-Pe pairs
    zeroD        D = 0 split tracer: exact M = 0 (no transverse flux in a
                 straight duct), so any M is spurious transverse transport

Acceptance values are C1-C4 of `.agent/decisions/2026-10-15-F17-SCIENCE-VALUES-01.md`.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sl

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

W, H, L = 300e-6, 100e-6, 0.01
MU = 0.001


def duct_flow_factor(width=W, height=H, terms=401):
    """Q = factor * G / mu for a rectangular duct (width >= height)."""
    s = sum(
        math.tanh(n * math.pi * width / (2 * height)) / n**5
        for n in range(1, terms + 1, 2)
    )
    return width * height**3 / 12 * (1 - 192 * height / (math.pi**5 * width) * s)


def developed_gradient_pa_m(q_m3_s, width=W, height=H):
    return q_m3_s * MU / duct_flow_factor(width, height)


def series_velocity(y, z, width=W, height=H, terms=201):
    """Fully developed axial velocity shape (arbitrary scale) at (y, z)."""
    a, b = height / 2, width / 2
    zz, yy = z - a, y - b
    u = np.zeros(np.broadcast(y, z).shape)
    for n in range(1, terms + 1, 2):
        k = n * math.pi / (2 * a)
        ratio = (
            np.exp(k * (np.abs(yy) - b))
            * (1 + np.exp(-2 * k * np.abs(yy)))
            / (1 + np.exp(-2 * k * b))
        )
        u += (-1) ** ((n - 1) // 2) / n**3 * (1 - ratio) * np.cos(k * zz)
    return u


def marching_mixing(q_m3_s, d_m2_s, ny=150, nz=50, dx=5e-6, length=L):
    """Independent split-tracer outlet M: u c_x = D (c_yy + c_zz), no-flux walls.

    Cell-centred cross-section, developed series velocity scaled to Q,
    Rannacher start (4 implicit Euler steps) then Crank-Nicolson.
    """
    hy, hz = W / ny, H / nz
    yc = (np.arange(ny) + 0.5) * hy
    zc = (np.arange(nz) + 0.5) * hz
    Y, Z = np.meshgrid(yc, zc, indexing="ij")
    u = series_velocity(Y, Z)
    u *= q_m3_s / (u.sum() * hy * hz)
    u = u.ravel()
    c = (Y.ravel() > W / 2).astype(float)
    if d_m2_s == 0:
        flux = u * hy * hz
        mean = (flux * c).sum() / flux.sum()
        var = (flux * (c - mean) ** 2).sum() / flux.sum()
        return 1 - math.sqrt(var / 0.25)

    def lap1d(n, h):
        main = np.full(n, -2.0)
        main[0] = main[-1] = -1.0
        return sp.diags([np.ones(n - 1), main, np.ones(n - 1)], [-1, 0, 1]) / h**2

    lap = sp.kron(lap1d(ny, hy), sp.eye(nz)) + sp.kron(sp.eye(ny), lap1d(nz, hz))
    lap = (d_m2_s * lap).tocsc()
    mass = sp.diags(u / dx).tocsc()
    implicit = sl.splu((mass - lap).tocsc())
    cn_left = sl.splu((mass - 0.5 * lap).tocsc())
    cn_right = (mass + 0.5 * lap).tocsc()
    steps = round(length / dx)
    for k in range(steps):
        if k < 4:
            c = implicit.solve(mass @ c)
        else:
            c = cn_left.solve(cn_right @ c)
    flux = u * hy * hz
    mean = (flux * c).sum() / flux.sum()
    var = (flux * (c - mean) ** 2).sum() / flux.sum()
    return 1 - math.sqrt(var / 0.25)


def reference_mixing(q_m3_s, d_m2_s):
    """Marching M at two cross-section/axial resolutions (self-convergence)."""
    coarse = marching_mixing(q_m3_s, d_m2_s, ny=150, nz=50, dx=5e-6)
    fine = marching_mixing(q_m3_s, d_m2_s, ny=300, nz=100, dx=2.5e-6)
    return {"M_ref": fine, "M_ref_coarse": coarse, "self_delta": abs(fine - coarse)}

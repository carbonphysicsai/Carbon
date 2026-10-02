"""A full-vector finite-difference mode solver for dielectric waveguides.

Carbon's own implementation of the standard 2D Yee-grid FDFD eigenproblem for
modes travelling along z (R. C. Rumpf, "Electromagnetic and Photonic
Simulation for the Beginner", Artech House 2022, ch. on FDFD waveguide
analysis; Zhu and Brown, Opt. Express 10(17), 2002). Lengths are normalized by
k0 = 2 pi / lambda; mu = 1 everywhere; the boundary is a perfect electric
conductor (tangential E = 0) placed far enough from the cores that the guided
modes do not feel it (checked by the caller's convergence study).

Fields on the Yee grid, cell (i, j) with x index i and y index j:
  Ex at (i+1/2, j), Ey at (i, j+1/2), Ez at (i, j)
  Hx at (i, j+1/2), Hy at (i+1/2, j), Hz at (i+1/2, j+1/2)
Permittivity is sampled on the doubled grid (`eps2`, shape 2Nx x 2Ny):
  eps_xx = eps2[1::2, 0::2], eps_yy = eps2[0::2, 1::2], eps_zz = eps2[0::2, 0::2].

With E and the normalized H~ = -i eta0 H, and fields varying as exp(-gamma z):
  P = [[DEX Ezz^-1 DHY,        -(DEX Ezz^-1 DHX + I)],
       [DEY Ezz^-1 DHY + I,     -DEY Ezz^-1 DHX     ]]
  Q = [[DHX DEY,               -(DHX DEX + Eyy)     ],
       [DHY DEY + Exx,          -DHY DEX            ]]
  (P Q) [ex; ey] = gamma^2 [ex; ey],   n_eff = sqrt(-gamma^2),
and [hx; hy] = Q [ex; ey] / gamma. DEX, DEY are forward differences of E with
zero beyond the boundary; DHX = -DEX^T, DHY = -DEY^T.

numpy and scipy only (the repository's locked `science-jax` group).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


@dataclass(frozen=True)
class Mode:
    n_eff: float
    ex: np.ndarray  # (Nx, Ny), at Ex positions
    ey: np.ndarray
    hx: np.ndarray  # normalized H~ = -i eta0 H, at Hx positions
    hy: np.ndarray
    te_fraction: float  # share of |E_t|^2 in Ex


def _difference(n, step):
    """Forward difference with zero beyond the last point."""
    return sp.diags([-np.ones(n), np.ones(n - 1)], [0, 1], shape=(n, n)) / step


def operators(eps2, dx, dy, wavelength):
    """P and Q for permittivity `eps2` on the doubled grid; lengths in the
    same unit as `wavelength`."""
    k0 = 2 * np.pi / wavelength
    nx, ny = eps2.shape[0] // 2, eps2.shape[1] // 2
    exx = eps2[1::2, 0::2].ravel()
    eyy = eps2[0::2, 1::2].ravel()
    ezz = eps2[0::2, 0::2].ravel()
    ix, iy = sp.identity(nx), sp.identity(ny)
    dex = sp.kron(_difference(nx, k0 * dx), iy).tocsr()
    dey = sp.kron(ix, _difference(ny, k0 * dy)).tocsr()
    dhx, dhy = -dex.T.tocsr(), -dey.T.tocsr()
    izz = sp.diags(1.0 / ezz)
    eye = sp.identity(nx * ny)
    p = sp.bmat(
        [
            [dex @ izz @ dhy, -(dex @ izz @ dhx + eye)],
            [dey @ izz @ dhy + eye, -(dey @ izz @ dhx)],
        ]
    ).tocsc()
    q = sp.bmat(
        [
            [dhx @ dey, -(dhx @ dex + sp.diags(eyy))],
            [dhy @ dey + sp.diags(exx), -(dhy @ dex)],
        ]
    ).tocsc()
    return p, q


def solve(eps2, dx, dy, wavelength, count, n_guess):
    """The `count` modes with n_eff nearest `n_guess` from above, highest
    first. Guided modes only: n_eff must exceed the smallest index present."""
    p, q = operators(eps2, dx, dy, wavelength)
    omega2 = (p @ q).tocsc()
    nx, ny = eps2.shape[0] // 2, eps2.shape[1] // 2
    # A fixed pseudo-random start vector makes the solve bit-reproducible; a
    # constant one would be orthogonal to every odd mode.
    start = np.random.default_rng(0).standard_normal(omega2.shape[0])
    values, vectors = spla.eigs(
        omega2, k=count, sigma=-(n_guess**2), which="LM", v0=start
    )
    modes = []
    for value, vector in zip(values, vectors.T):
        n2 = -value
        if abs(n2.imag) > 1e-8 * abs(n2.real):
            raise ValueError(f"complex n_eff^2 {n2}: not a guided mode")
        n_eff = float(np.sqrt(n2.real))
        gamma = 1j * n_eff
        h = (q @ vector) / gamma
        ex, ey = vector[: nx * ny], vector[nx * ny :]
        hx, hy = h[: nx * ny], h[nx * ny :]
        e2x, e2y = np.sum(abs(ex) ** 2), np.sum(abs(ey) ** 2)
        modes.append(
            Mode(
                n_eff,
                ex.reshape(nx, ny),
                ey.reshape(nx, ny),
                hx.reshape(nx, ny),
                hy.reshape(nx, ny),
                float(e2x / (e2x + e2y)),
            )
        )
    return sorted(modes, key=lambda m: -m.n_eff)


def power_overlap(a, b, dx, dy):
    """1/2 integral of (E_a x H_b*) . z, in units where eta0 = 1, so that a
    mode's own overlap is its (real, positive) power. The solver's H~ is
    -i eta0 H, hence the factor -i. Ex and Hy share positions on the Yee
    grid, and so do Ey and Hx, so the products need no interpolation."""
    return -0.5j * dx * dy * np.sum(a.ex * np.conj(b.hy) - a.ey * np.conj(b.hx))


def normalized(mode, dx, dy, core_mask):
    """The mode scaled to unit power, with its sign fixed: the integral of
    Re(Ex) over `core_mask` (a boolean array on the Ex grid) is positive.
    That is the phase convention the S-parameters inherit."""
    power = power_overlap(mode, mode, dx, dy)
    scale = 1 / np.sqrt(power)
    # Make the dominant field real and positive in the core.
    phase = np.sum((mode.ex * scale)[core_mask])
    scale *= np.conj(phase) / abs(phase)
    return Mode(
        mode.n_eff,
        mode.ex * scale,
        mode.ey * scale,
        mode.hx * scale,
        mode.hy * scale,
        mode.te_fraction,
    )

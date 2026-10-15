"""Axisymmetric mode matching for coaxial f13 silencers (F13-SCIENCE-VALUES-01 B3).

An independent control for the Elmer route on coaxial geometries: a chain
of rigid-walled coaxial cylinders with semi-infinite matched inlet/outlet
ducts, exp(+i*omega*t), forward modes exp(-i*k_n*z). Each section carries
the axisymmetric rigid-duct modes J0(alpha_n r / a) (alpha_n the zeros of J1,
alpha_0 = 0), propagating and evanescent; at each step, pressure is matched
over the smaller area (projected on its modes) and axial velocity over the
larger area (zero on the annulus wall). The global system is solved per
frequency; R and T are the plane-mode amplitudes, so 1 - |R|^2 - |T|^2 checks
power. Mode counts scale with radius (N per 25 mm); convergence is checked
by doubling N. Offset necks are outside this model (it abstains).
"""

from __future__ import annotations

import cmath
import functools
import math

import numpy as np
from scipy.special import j0, j1, jn_zeros

RHO, C = 1.2, 343.0
R_PORT, R_NECK = 25.0, 20.0


def sections(case):
    """[(radius_m, length_m)] from the packet geometry (coaxial only)."""
    if case.get("neck_offset_mm", 0) != 0:
        raise ValueError("mode matching abstains: offset neck is not axisymmetric")
    out = [(R_PORT, 0.0), (case["radius1_mm"], case["length1_mm"])]
    if case.get("neck_length_mm", 0) > 0:
        out.append((R_NECK, case["neck_length_mm"]))
    if case.get("radius2_mm", 0) > 0:
        out.append((case["radius2_mm"], case["length2_mm"]))
    out.append((R_PORT, 0.0))
    return [(r * 1e-3, length * 1e-3) for r, length in out]


@functools.cache
def _modes(a, n):
    alpha = np.concatenate([[0.0], jn_zeros(1, n - 1)]) if n > 1 else np.array([0.0])
    return alpha / a, (a * a / 2) * j0(alpha) ** 2


def _kz(k, q):
    d = k * k - q * q
    return np.where(d >= 0, np.sqrt(np.abs(d)), -1j * np.sqrt(np.abs(d)))


def _coupling(a_small, q_small, q_large):
    """C[m, n] = integral_0^a_small J0(q_s,m r) J0(q_l,n r) r dr."""
    p = q_small[:, None]
    q = q_large[None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        c = (a_small * (p * j1(p * a_small) * j0(q * a_small)
                        - q * j0(p * a_small) * j1(q * a_small)) / (p * p - q * q))  # fmt: skip
    same = np.isclose(p, q, rtol=1e-12, atol=1e-9) & np.ones_like(c, dtype=bool)
    if same.any():
        # equal wavenumbers: (a^2/2)(J0(pa)^2 + J1(pa)^2)
        pa = (p * a_small) * np.ones_like(c)
        c = np.where(same, a_small**2 / 2 * (j0(pa) ** 2 + j1(pa) ** 2), c)
    return c


def solve(case, frequency_hz, n_port=20):
    """Complex (R, T) at the first and last junction planes."""
    secs = sections(case)
    k = 2 * math.pi * frequency_hz / C
    ns = [max(2, round(n_port * a / (R_PORT * 1e-3))) for a, _ in secs]
    modes = [_modes(a, n) for (a, _), n in zip(secs, ns)]
    kz = [_kz(k, q) for q, _ in modes]
    # unknown layout: inlet B, then (A, B) per interior section, then outlet A
    offs, size = [], 0
    for i, n in enumerate(ns):
        offs.append(size)
        size += n if i in (0, len(ns) - 1) else 2 * n
    m = np.zeros((size, size), complex)
    rhs = np.zeros(size, complex)
    row = 0
    for j in range(len(secs) - 1):
        left, right = j, j + 1
        a_l, a_r = secs[left][0], secs[right][0]
        n_l, n_r = ns[left], ns[right]
        # amplitudes at the junction as (forward coeff, backward coeff) maps
        # left: A_L e^{-ik L_L} (A referenced at section start), B_L (at end)
        # right: A_R (at start), B_R e^{-ik L_R} (referenced at its end)

        def fwd_bwd(sec, at_end):
            n = ns[sec]
            ka = kz[sec]
            first, last = sec == 0, sec == len(secs) - 1
            length = secs[sec][1]
            fa = np.zeros((n, size), complex)
            fb = np.zeros((n, size), complex)
            src_a = np.zeros(n, complex)
            if first:  # A known (incident plane wave, amplitude 1 at z=0)
                src_a[0] = 1.0
                fb[:, offs[sec] : offs[sec] + n] = np.eye(n)
            elif last:
                fa[:, offs[sec] : offs[sec] + n] = np.eye(n)
            else:
                ea = np.exp(-1j * ka * length) if at_end else np.ones(n)
                eb = np.ones(n) if at_end else np.exp(-1j * ka * length)
                fa[:, offs[sec] : offs[sec] + n] = np.diag(ea)
                fb[:, offs[sec] + n : offs[sec] + 2 * n] = np.diag(eb)
            return fa, fb, src_a

        la, lb, lsrc = fwd_bwd(left, True)
        ra, rb, rsrc = fwd_bwd(right, False)
        small_is_left = a_l <= a_r
        q_l, nrm_l = modes[left]
        q_r, nrm_r = modes[right]
        if small_is_left:
            cpl = _coupling(a_l, q_l, q_r)  # (n_l, n_r)
            # pressure on small (left) modes: C P_R = N_L P_L
            m[row : row + n_l] += cpl @ (ra + rb) - np.diag(nrm_l) @ (la + lb)
            rhs[row : row + n_l] += -(cpl @ rsrc) + nrm_l * lsrc
            row += n_l
            # velocity on large (right) modes: N_R U_R = C^T U_L
            ul, ur = kz[left], kz[right]
            m[row : row + n_r] += np.diag(nrm_r * ur) @ (ra - rb) - cpl.T @ np.diag(
                ul
            ) @ (la - lb)
            rhs[row : row + n_r] += -(nrm_r * ur * rsrc) + cpl.T @ (ul * lsrc)
            row += n_r
        else:
            cpl = _coupling(a_r, q_r, q_l)  # (n_r, n_l)
            m[row : row + n_r] += cpl @ (la + lb) - np.diag(nrm_r) @ (ra + rb)
            rhs[row : row + n_r] += -(cpl @ lsrc) + nrm_r * rsrc
            row += n_r
            ul, ur = kz[left], kz[right]
            m[row : row + n_l] += np.diag(nrm_l * ul) @ (la - lb) - cpl.T @ np.diag(
                ur
            ) @ (ra - rb)
            rhs[row : row + n_l] += -(nrm_l * ul * lsrc) + cpl.T @ (ur * rsrc)
            row += n_l
    x = np.linalg.solve(m, rhs)
    r = complex(x[offs[0]])
    t = complex(x[offs[-1]])
    return r, t


def curve(case, freqs, n_port=20, plane_offset_m=0.01):
    """Rows like the Elmer observer: TL, complex r/t at the 10 mm panel
    planes (plane_offset_m outside each chamber), plane power residual."""
    out = []
    for f in freqs:
        r, t = solve(case, f, n_port)
        k = 2 * math.pi * f / C
        shift = cmath.exp(-2j * k * plane_offset_m)
        r, t = r * shift, t * shift
        pt = abs(t) ** 2
        out.append({
            "frequency_hz": f, "r": [r.real, r.imag], "t": [t.real, t.imag],
            "tl_db": -10 * math.log10(pt), "transmitted_w": pt, "reflected_w": abs(r) ** 2,
            "signed_plane_residual": 1 - pt - abs(r) ** 2,
        })  # fmt: skip
    return out

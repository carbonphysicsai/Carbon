"""Public smooth periodic Burgers fixture, separate from the training code.

u_t + u*u_x = nu*u_xx on [0,L), periodic; nu>0; no source.
Reference: Cole-Hopf heat evolution plus Galilean mean shift, evaluated by
Fourier quadrature. This implementation and its sample law are unqualified.
"""

from __future__ import annotations

import numpy as np
from scipy.integrate import solve_ivp

from .data import Trajectories, assert_case_disjoint, subset


def initial_from_coefficients(x, a, b, mean=0.0, L=1.0):
    k = np.arange(1, len(a) + 1)
    phase = 2 * np.pi * np.outer(x / L, k)
    return mean + np.sin(phase) @ a + np.cos(phase) @ b


def cole_hopf(a, b, mean, nu, times, nx=64, work_grid=512, L=1.0):
    if nu <= 0 or work_grid % nx or work_grid < 2 * nx:
        raise ValueError("reference parameters")
    xx = np.arange(work_grid) * L / work_grid
    harmonics = np.arange(1, len(a) + 1)
    kk = 2 * np.pi * harmonics / L
    phase = np.outer(xx, kk)
    potential = -(np.cos(phase) @ (a / kk)) + (np.sin(phase) @ (b / kk))
    exponent = -potential / (2 * nu)
    exponent -= exponent.max()
    phi0 = np.exp(exponent)
    coefficients = np.fft.fft(phi0)
    k = 2 * np.pi * np.fft.fftfreq(work_grid, d=L / work_grid)
    outputs = []
    for t in times:
        if t < 0:
            raise ValueError("negative time")
        evolved = coefficients * np.exp(-nu * k * k * t - 1j * k * mean * t)
        phi = np.fft.ifft(evolved).real
        phix = np.fft.ifft(1j * k * evolved).real
        if not np.isfinite(phi).all() or np.min(phi) <= 1e-12:
            raise FloatingPointError(
                "Cole-Hopf conditioning outside this fixture's reliable range"
            )
        outputs.append((mean - 2 * nu * phix / phi)[:: work_grid // nx])
    return np.asarray(outputs, dtype=np.float64)


def generate_splits(
    train_cases=64, validation_cases=16, audit_cases=16, nx=64, nt=9, seed=20260912
):
    """Explicit demonstration population, not Carbon Challenge law.

    Four smooth Fourier harmonics, decaying amplitudes; nu uniform [.03,.08],
    mean uniform [-.1,.1], times [0,.3]. Whole-case splits precede any pairing.
    """
    rng = np.random.default_rng(seed)
    x = np.arange(nx, dtype=np.float64) / nx
    times = np.linspace(0.0, 0.3, nt)
    aa = []
    bb = []
    means = []
    nus = []
    ys = []
    u0 = []
    n = train_cases + validation_cases + audit_cases
    for _ in range(n):
        amplitude = rng.uniform(0.25, 0.65)
        scale = amplitude / (np.arange(1, 5) ** 2)
        a = rng.normal(size=4) * scale
        b = rng.normal(size=4) * scale
        mean = rng.uniform(-0.1, 0.1)
        nu = rng.uniform(0.03, 0.08)
        u = initial_from_coefficients(x, a, b, mean)
        y = cole_hopf(a, b, mean, nu, times, nx=nx, work_grid=max(512, 8 * nx))
        u0.append(u)
        ys.append(y)
        nus.append(nu)
        aa.append(a)
        bb.append(b)
        means.append(mean)
    provenance = f"PUBLIC_UNQUALIFIED_cole_hopf_demo_v1_seed_{seed}"
    all_data = Trajectories(
        np.array(u0),
        np.array(nus),
        np.broadcast_to(times, (n, nt)),
        np.array(ys),
        x,
        "train",
        provenance,
    )
    a = train_cases
    b = a + validation_cases
    splits = (
        subset(all_data, np.arange(a), "train"),
        subset(all_data, np.arange(a, b), "validation"),
        subset(all_data, np.arange(b, n), "audit"),
    )
    assert_case_disjoint(*splits)
    metadata = {
        "a": np.array(aa),
        "b": np.array(bb),
        "mean": np.array(means),
        "nu": np.array(nus),
        "times": times,
    }
    return splits, metadata


def spectral_ivp_witness(a, b, mean, nu, times, n=128, L=1.0):
    """Different solution method; shared FFT/library/authoring is disclosed.

    Conservative pseudo-spectral method of lines, 2/3 filter, DOP853.
    These rtol/atol values are development probe settings, not solver acceptance.
    """
    x = np.arange(n) * L / n
    u0 = initial_from_coefficients(x, a, b, mean, L)
    k = 2 * np.pi * np.fft.fftfreq(n, d=L / n)
    filt = np.abs(np.fft.fftfreq(n) * n) < n / 3

    def rhs(t, u):
        uh = np.fft.fft(u)
        filtered = np.fft.ifft(uh * filt).real
        nonlinear = np.fft.fft(0.5 * filtered**2) * filt
        return np.fft.ifft(-1j * k * nonlinear - nu * k * k * uh).real

    sol = solve_ivp(
        rhs,
        (0.0, float(times[-1])),
        u0,
        t_eval=times,
        method="DOP853",
        rtol=1e-9,
        atol=1e-11,
    )
    if not sol.success:
        raise RuntimeError(sol.message)
    return sol.y.T, {
        "method": "spectral_MOL_DOP853",
        "nfev": sol.nfev,
        "n": n,
        "rtol": 1e-9,
        "atol": 1e-11,
    }

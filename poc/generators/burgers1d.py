"""Burgers-1D data generator with Fourier pseudo-spectral reference solver.

Roles: train | eval | stress — same code, different seeds and envelopes.
Generator version: burgers1d_v0.1
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Literal, Optional, Tuple

import numpy as np
import yaml

Role = Literal["train", "eval", "stress"]

GENERATOR_VERSION = "burgers1d_v0.1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_challenge_config(fast: bool = False) -> dict:
    path = _repo_root() / "poc" / "configs" / "challenge_burgers1d.yaml"
    with open(path) as f:
        cfg = yaml.safe_load(f)
    if fast:
        for k, v in cfg.get("fast", {}).items():
            if k in ("nx",):
                cfg["domain"]["nx"] = v
            elif k == "t_final":
                cfg["domain"]["t_final"] = v
            elif k in ("n_train", "n_eval", "n_stress"):
                cfg["splits"][k] = v
    return cfg


def role_seed(
    challenge_id: str,
    role: Role,
    local_nonce: int | str = 0,
    run_id: str = "",
) -> int:
    material = f"{challenge_id}|{role}|{local_nonce}|{run_id}"
    return int(hashlib.sha256(material.encode()).hexdigest(), 16) % (2**63 - 1)


def payload_hash(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()[:16]


@dataclass
class BurgersBatch:
    u0: np.ndarray       # (N, nx)
    uT: np.ndarray       # (N, nx)
    nu: np.ndarray       # (N,)
    x: np.ndarray        # (nx,)
    seed: int
    role: str
    generator_version: str = GENERATOR_VERSION

    def hash(self) -> str:
        return payload_hash(self.uT)


def _sample_ics(
    rng: np.random.Generator,
    n: int,
    nx: int,
    n_modes: int,
    coeff_bound: float,
) -> np.ndarray:
    """Sum-of-sines ICs on [0,1] periodic grid."""
    x = np.linspace(0.0, 1.0, nx, endpoint=False)
    u0 = np.zeros((n, nx), dtype=np.float64)
    for i in range(n):
        for k in range(1, n_modes + 1):
            a = rng.uniform(-coeff_bound, coeff_bound)
            b = rng.uniform(-coeff_bound, coeff_bound)
            u0[i] += a * np.sin(2 * np.pi * k * x) + b * np.cos(2 * np.pi * k * x)
    return u0, x


def burgers_reference_solve(
    u0: np.ndarray,
    nu: float,
    t_final: float,
    n_steps: int = 200,
) -> np.ndarray:
    """Fourier pseudo-spectral ETDRK-style integration for 1D viscous Burgers.

    Periodic domain assumed. Operates on a single 1D field (nx,).
    """
    nx = u0.shape[-1]
    k = 2 * np.pi * np.fft.fftfreq(nx, d=1.0 / nx)
    k2 = k**2
    dt = t_final / n_steps

    u_hat = np.fft.fft(u0.astype(np.float64))
    # Linear propagator for viscosity term
    L = -nu * k2
    # Avoid division by zero at k=0
    E = np.exp(L * dt)
    E2 = np.exp(L * dt / 2)

    def N(uh):
        u = np.fft.ifft(uh).real
        ux = np.fft.ifft(1j * k * uh).real
        return -np.fft.fft(u * ux)

    for _ in range(n_steps):
        # 2nd-order exponential time differencing (ETD2RK-ish)
        a = N(u_hat)
        u_a = E2 * u_hat + (E2 - 1) / (L + 1e-16) * a
        u_a[0] = u_hat[0] + dt / 2 * a[0]  # k=0 special
        b = N(u_a)
        u_hat = E * u_hat + (E - 1) / (L + 1e-16) * b
        u_hat[0] = u_hat[0]  # mean evolves via nonlinear (should stay ~const)

    return np.fft.ifft(u_hat).real


def generate_batch(
    role: Role,
    local_nonce: int | str = 0,
    run_id: str = "poc",
    fast: bool = False,
    n: Optional[int] = None,
) -> BurgersBatch:
    cfg = load_challenge_config(fast=fast)
    challenge_id = cfg["challenge_id"]
    seed = role_seed(challenge_id, role, local_nonce, run_id)
    rng = np.random.default_rng(seed)

    nx = int(cfg["domain"]["nx"])
    t_final = float(cfg["domain"]["t_final"])
    n_modes = int(cfg["ic"]["n_modes"])

    if n is None:
        n = int(cfg["splits"][f"n_{role}"])

    nu_lo, nu_hi = cfg["viscosity"][role]
    coeff_bound = float(cfg["ic"][f"coeff_bound_{role}"])

    u0, x = _sample_ics(rng, n, nx, n_modes, coeff_bound)
    nu = rng.uniform(nu_lo, nu_hi, size=n)

    uT = np.zeros_like(u0)
    n_steps = 80 if fast else 200
    for i in range(n):
        uT[i] = burgers_reference_solve(u0[i], float(nu[i]), t_final, n_steps=n_steps)

    return BurgersBatch(
        u0=u0.astype(np.float32),
        uT=uT.astype(np.float32),
        nu=nu.astype(np.float32),
        x=x.astype(np.float32),
        seed=seed,
        role=role,
        generator_version=GENERATOR_VERSION,
    )

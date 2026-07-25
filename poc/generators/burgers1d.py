"""Burgers-1D data generator with stable IMEX Fourier reference solver.

Roles: train | eval | stress — same code, different seeds and envelopes.
Generator version: burgers1d_v0.3 (IMEX + dealias; was v0.2 RK4)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, Tuple

import numpy as np
import yaml

Role = Literal["train", "eval", "stress"]

GENERATOR_VERSION = "burgers1d_v0.3"


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
    u0: np.ndarray  # (N, nx)
    uT: np.ndarray  # (N, nx)
    nu: np.ndarray  # (N,)
    x: np.ndarray  # (nx,)
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
) -> Tuple[np.ndarray, np.ndarray]:
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
    n_steps: int | None = None,
) -> np.ndarray:
    """IMEX Fourier Burgers: explicit advection + implicit viscosity + 2/3 dealias.

    ∂t u + u ∂x u = ν ∂xx u  on periodic [0,1].
    """
    nx = int(u0.shape[-1])
    k = 2 * np.pi * np.fft.fftfreq(nx, d=1.0 / nx)
    k2 = k**2
    if n_steps is None:
        n_steps = max(150, int(150 * t_final / max(float(nu), 1e-3)))
    dt = t_final / max(n_steps, 1)
    u = np.asarray(u0, dtype=np.float64).copy()
    mask = np.ones(nx, dtype=np.float64)
    mask[nx // 3 : 2 * nx // 3] = 0.0

    for _ in range(n_steps):
        uh = np.fft.fft(u) * mask
        u = np.fft.ifft(uh).real
        ux = np.fft.ifft(1j * k * uh).real
        adv_hat = np.fft.fft(-u * ux) * mask
        uh = np.fft.fft(u)
        uh = (uh + dt * adv_hat) / (1.0 + dt * float(nu) * k2)
        u = np.fft.ifft(uh).real
        if not np.isfinite(u).all():
            u = np.nan_to_num(u, nan=0.0, posinf=0.0, neginf=0.0)

    return u


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
    for i in range(n):
        uT[i] = burgers_reference_solve(u0[i], float(nu[i]), t_final)

    return BurgersBatch(
        u0=u0.astype(np.float32),
        uT=uT.astype(np.float32),
        nu=nu.astype(np.float32),
        x=x.astype(np.float32),
        seed=seed,
        role=role,
        generator_version=GENERATOR_VERSION,
    )

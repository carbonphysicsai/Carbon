"""Burgers-1D procedural generator — trustless, publicly seeded.

Seed hierarchy (aligned with carbon.common.seeds):
  master = hash(challenge_id ‖ block_hash ‖ run_nonce)
  role streams: train / eval / stress are distinct splitmix streams

Same code path for miner local loops and validator eval.
Only the seed *inputs* differ (local nonce vs chain block_hash).

Generator version: burgers1d_v0.4
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple

import numpy as np
import yaml

from carbon.common.seeds import derive_master_seed, derive_role_seed, splitmix64

Role = Literal["train", "eval", "stress"]

GENERATOR_VERSION = "burgers1d_v0.4"

# Fixed stream indices — never reorder without version bump
_ROLE_STREAM = {"train": 10, "eval": 11, "stress": 12}


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


def payload_hash(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()[:16]


def resolve_role_seed(
    role: Role,
    *,
    challenge_id: str,
    block_hash: str = "local",
    run_nonce: int | str = 0,
    local_mode: bool = True,
) -> Tuple[int, Dict[str, Any]]:
    """Derive role seed + public provenance for the batch card.

    local_mode=True  → derive_role_seed(challenge, role, nonce, run)  [miner loops]
    local_mode=False → master from block_hash, then splitmix role stream [official]
    """
    if local_mode:
        seed = derive_role_seed(challenge_id, role, run_nonce, str(block_hash))
        prov = {
            "mode": "local",
            "challenge_id": challenge_id,
            "role": role,
            "run_nonce": run_nonce,
            "block_hash": block_hash,
            "formula": "sha256(challenge_id|role|run_nonce|block_hash)",
        }
    else:
        master = derive_master_seed(challenge_id, block_hash, run_nonce)
        seed = splitmix64(master, _ROLE_STREAM[role])
        prov = {
            "mode": "official",
            "challenge_id": challenge_id,
            "role": role,
            "run_nonce": run_nonce,
            "block_hash": block_hash,
            "master_seed": master,
            "stream": _ROLE_STREAM[role],
            "formula": "splitmix64(master(challenge|block|nonce), role_stream)",
        }
    return seed, prov


@dataclass
class BurgersBatch:
    u0: np.ndarray  # (N, nx)
    uT: np.ndarray  # (N, nx)
    nu: np.ndarray  # (N,)
    x: np.ndarray  # (nx,)
    seed: int
    role: str
    generator_version: str = GENERATOR_VERSION
    provenance: Dict[str, Any] = field(default_factory=dict)
    envelope: Dict[str, Any] = field(default_factory=dict)

    def hash(self) -> str:
        return payload_hash(self.uT)

    def assert_finite(self) -> None:
        if not (np.isfinite(self.u0).all() and np.isfinite(self.uT).all()):
            raise RuntimeError(
                f"non-finite procedural data role={self.role} seed={self.seed}"
            )


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
    """IMEX Fourier Burgers: explicit advection + implicit viscosity + 2/3 dealias."""
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
    *,
    block_hash: str = "local",
    local_mode: bool = True,
    challenge_id: Optional[str] = None,
) -> BurgersBatch:
    """Procedural batch for role ∈ {train, eval, stress}.

    Official eval: pass block_hash=<chain hash>, local_mode=False.
    Miner local loop: default local_mode=True, block_hash can be run_id tag.
    """
    cfg = load_challenge_config(fast=fast)
    cid = challenge_id or cfg["challenge_id"]
    # local_nonce maps to run_nonce; run_id kept as tag in provenance
    seed, prov = resolve_role_seed(
        role,
        challenge_id=cid,
        block_hash=block_hash if not local_mode else str(run_id),
        run_nonce=local_nonce,
        local_mode=local_mode,
    )
    prov["run_id"] = run_id
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

    envelope = {
        "nx": nx,
        "t_final": t_final,
        "n": n,
        "n_modes": n_modes,
        "nu_range": [float(nu_lo), float(nu_hi)],
        "coeff_bound": float(coeff_bound),
        "role": role,
    }

    batch = BurgersBatch(
        u0=u0.astype(np.float32),
        uT=uT.astype(np.float32),
        nu=nu.astype(np.float32),
        x=x.astype(np.float32),
        seed=seed,
        role=role,
        generator_version=GENERATOR_VERSION,
        provenance=prov,
        envelope=envelope,
    )
    batch.assert_finite()
    return batch

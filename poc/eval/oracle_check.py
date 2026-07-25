"""Oracle cross-check for Burgers procedural generator.

Trustless Verification §4: quality via generator validation, not fixed test sets.
PoC oracle = same PDE, higher-resolution time integration (more IMEX steps).
Fails if mean relative error between production solver and oracle exceeds tau.

Production later: swap oracle for FEniCS / DifferentialEquations.jl bindings.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from poc.generators.burgers1d import burgers_reference_solve, generate_batch

ORACLE_TAU_REL = 0.05  # 5% mean rel error vs refined integrator


def _oracle_solve(u0: np.ndarray, nu: float, t_final: float) -> np.ndarray:
    """Refined time grid (4× steps of production default)."""
    # production uses ~150 * t_final / nu steps; oracle uses 4×
    n_steps = max(600, int(600 * t_final / max(nu, 1e-3)))
    return burgers_reference_solve(u0, nu, t_final, n_steps=n_steps)


def cross_check_generator(
    *,
    n_samples: int = 8,
    seed_nonce: int = 0,
    tau: float = ORACLE_TAU_REL,
    fast: bool = True,
) -> Dict[str, Any]:
    """Sample train-envelope ICs; compare production uT vs oracle uT."""
    batch = generate_batch(
        "train", local_nonce=seed_nonce, run_id="oracle", fast=fast, n=n_samples
    )
    rels: List[float] = []
    for i in range(batch.u0.shape[0]):
        cfg_t = 0.5 if fast else 1.0
        # recover t_final from challenge via batch envelope if present
        t_final = float(batch.envelope.get("t_final", cfg_t)) if batch.envelope else cfg_t
        prod = batch.uT[i]
        ora = _oracle_solve(batch.u0[i], float(batch.nu[i]), t_final)
        num = float(np.linalg.norm(prod - ora))
        den = float(np.linalg.norm(ora) + 1e-12)
        rels.append(num / den)

    mean_rel = float(np.mean(rels))
    max_rel = float(np.max(rels))
    passed = mean_rel <= tau
    return {
        "passed": passed,
        "mean_rel": mean_rel,
        "max_rel": max_rel,
        "tau": tau,
        "n_samples": n_samples,
        "rels": rels,
        "note": "oracle=IMEX 4× steps; replace with FEniCS/DiffEq.jl in Phase 0 hardening",
    }

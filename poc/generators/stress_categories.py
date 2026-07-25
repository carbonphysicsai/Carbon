"""Burgers-1D stress category suite — Data_Management §5 / SPEC stress weights.

Categories (weights sum to 1.0):
  extended_envelope  0.30
  shock_perturbation 0.20
  high_freq_noise    0.15   (BL-trip analogue for 1D Burgers)
  low_viscosity      0.15   (separation-trigger analogue)
  grid_perturbation  0.10   (mesh analogue: phase shift / subsample)
  ic_scale           0.10   (BC/IC amplitude analogue)

Coverage requirement: weighted presence ≥ 0.95 before scoring is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import numpy as np

from carbon.common.seeds import splitmix64
from poc.generators.burgers1d import (
    BurgersBatch,
    burgers_reference_solve,
    load_challenge_config,
    payload_hash,
    GENERATOR_VERSION,
)

# Fixed category table — version bump if weights change
STRESS_SPEC_VERSION = "burgers_stress_v1"

CATEGORIES: Dict[str, Dict[str, Any]] = {
    "extended_envelope": {
        "weight": 0.30,
        "nu_scale": (0.5, 0.8),       # lower viscosity than train
        "coeff_scale": (1.2, 1.6),
        "justification": "Wider viscosity/amplitude than train envelope; tests OOD generalization (Data_Mgmt extended envelope).",
    },
    "shock_perturbation": {
        "weight": 0.20,
        "nu_scale": (0.4, 0.7),
        "coeff_scale": (1.4, 1.8),
        "steepen": True,
        "justification": "Steeper IC gradients → stronger shock formation; conservation + residual under discontinuous features.",
    },
    "high_freq_noise": {
        "weight": 0.15,
        "noise_amp": (0.02, 0.08),
        "n_noise_modes": (6, 12),
        "justification": "High-frequency IC noise (1D analogue of BL trip); tests small-scale robustness.",
    },
    "low_viscosity": {
        "weight": 0.15,
        "nu_fixed_range": (3e-4, 8e-4),
        "justification": "Near-inviscid regime; stress energy/residual stability when dissipation is weak.",
    },
    "grid_perturbation": {
        "weight": 0.10,
        "phase_shift": True,
        "justification": "Spatial phase shift of IC (mesh-perturbation analogue on fixed grid).",
    },
    "ic_scale": {
        "weight": 0.10,
        "amp_scale": (1.3, 2.0),
        "justification": "IC amplitude scaling (loading/BC strength analogue).",
    },
}

COVERAGE_THRESHOLD = 0.95


@dataclass
class StressSuite:
    batches: Dict[str, BurgersBatch]
    weights: Dict[str, float]
    coverage: float
    categories_present: List[str]
    spec_version: str = STRESS_SPEC_VERSION
    seed: int = 0
    meta: Dict[str, Any] = field(default_factory=dict)

    def mean_rel_l2(self, metrics_by_cat: Dict[str, float]) -> float:
        num = 0.0
        den = 0.0
        for cat, w in self.weights.items():
            if cat in metrics_by_cat:
                num += w * metrics_by_cat[cat]
                den += w
        return num / max(den, 1e-12)


def _sample_base_ics(rng, n, nx, n_modes, coeff_bound):
    x = np.linspace(0.0, 1.0, nx, endpoint=False)
    u0 = np.zeros((n, nx), dtype=np.float64)
    for i in range(n):
        for k in range(1, n_modes + 1):
            a = rng.uniform(-coeff_bound, coeff_bound)
            b = rng.uniform(-coeff_bound, coeff_bound)
            u0[i] += a * np.sin(2 * np.pi * k * x) + b * np.cos(2 * np.pi * k * x)
    return u0, x


def _generate_category(
    cat: str,
    spec: dict,
    rng: np.random.Generator,
    n: int,
    nx: int,
    t_final: float,
    n_modes: int,
    base_coeff: float,
    base_nu: Tuple[float, float],
    seed: int,
) -> BurgersBatch:
    coeff = base_coeff * float(np.mean(spec.get("coeff_scale", (1.0, 1.0))))
    if "coeff_scale" in spec:
        lo, hi = spec["coeff_scale"]
        coeff = base_coeff * rng.uniform(lo, hi)

    u0, x = _sample_base_ics(rng, n, nx, n_modes, coeff)

    if spec.get("steepen"):
        # compress toward a front via tanh warping of cumulative energy
        u0 = np.tanh(2.5 * u0)

    if "noise_amp" in spec:
        amp = rng.uniform(*spec["noise_amp"])
        n_hi = int(rng.integers(*spec["n_noise_modes"]))
        for i in range(n):
            for k in range(n_modes + 1, n_hi + 1):
                a = rng.uniform(-amp, amp)
                u0[i] += a * np.sin(2 * np.pi * k * x)

    if spec.get("phase_shift"):
        shift = int(rng.integers(1, max(2, nx // 8)))
        u0 = np.roll(u0, shift, axis=-1)

    if "amp_scale" in spec:
        s = rng.uniform(*spec["amp_scale"])
        u0 = u0 * s

    if "nu_fixed_range" in spec:
        nu = rng.uniform(*spec["nu_fixed_range"], size=n)
    elif "nu_scale" in spec:
        lo, hi = spec["nu_scale"]
        nu = rng.uniform(base_nu[0] * lo, base_nu[1] * hi, size=n)
    else:
        nu = rng.uniform(base_nu[0], base_nu[1], size=n)

    uT = np.zeros_like(u0)
    for i in range(n):
        uT[i] = burgers_reference_solve(u0[i], float(nu[i]), t_final)

    batch = BurgersBatch(
        u0=u0.astype(np.float32),
        uT=uT.astype(np.float32),
        nu=nu.astype(np.float32),
        x=x.astype(np.float32),
        seed=seed,
        role=f"stress:{cat}",
        generator_version=GENERATOR_VERSION,
        provenance={"category": cat, "stress_spec": STRESS_SPEC_VERSION},
        envelope={"category": cat, **{k: v for k, v in spec.items() if k != "justification"}},
    )
    batch.assert_finite()
    return batch


def generate_stress_suite(
    stress_seed: int,
    *,
    fast: bool = False,
    n_per_category: int | None = None,
) -> StressSuite:
    """Build full stress suite from stress_seed (validator-only)."""
    cfg = load_challenge_config(fast=fast)
    nx = int(cfg["domain"]["nx"])
    t_final = float(cfg["domain"]["t_final"])
    n_modes = int(cfg["ic"]["n_modes"])
    base_coeff = float(cfg["ic"]["coeff_bound_train"])
    base_nu = tuple(cfg["viscosity"]["train"])
    n = n_per_category or (2 if fast else 4)

    batches: Dict[str, BurgersBatch] = {}
    weights: Dict[str, float] = {}
    present: List[str] = []

    for i, (cat, spec) in enumerate(CATEGORIES.items()):
        cat_seed = splitmix64(stress_seed, 100 + i)
        rng = np.random.default_rng(cat_seed)
        try:
            batches[cat] = _generate_category(
                cat, spec, rng, n, nx, t_final, n_modes, base_coeff, base_nu, cat_seed
            )
            weights[cat] = float(spec["weight"])
            present.append(cat)
        except Exception as e:  # pragma: no cover
            # Category failure reduces coverage
            weights[cat] = float(spec["weight"])

    coverage = sum(CATEGORIES[c]["weight"] for c in present)
    return StressSuite(
        batches=batches,
        weights={c: CATEGORIES[c]["weight"] for c in CATEGORIES},
        coverage=float(coverage),
        categories_present=present,
        seed=stress_seed,
        meta={
            "n_per_category": n,
            "threshold": COVERAGE_THRESHOLD,
            "payload_hashes": {c: batches[c].hash() for c in batches},
        },
    )


def coverage_ok(suite: StressSuite, threshold: float = COVERAGE_THRESHOLD) -> Tuple[bool, str]:
    if suite.coverage + 1e-9 >= threshold:
        return True, f"coverage={suite.coverage:.3f} ≥ {threshold}"
    missing = [c for c in CATEGORIES if c not in suite.categories_present]
    return False, f"coverage={suite.coverage:.3f} < {threshold}; missing={missing}"

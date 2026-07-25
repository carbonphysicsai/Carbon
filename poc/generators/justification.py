"""Scientific justification for Burgers-1D procedural parameters.

Trustless Verification §9 — every range has a stated physics rationale.
This is the PoC subset; expand per-physics as generators land.
"""

from __future__ import annotations

from typing import Any, Dict, List

JUSTIFICATION_VERSION = "burgers_justification_v1"

BURGERS_PARAM_JUSTIFICATION: List[Dict[str, Any]] = [
    {
        "param": "domain.nx",
        "range": [64, 128],
        "rationale": (
            "1D periodic grid resolution sufficient to resolve moderate shocks at "
            "ν≥5e-4 without requiring subgrid models; standard for FNO-1d Burgers benchmarks."
        ),
        "refs": ["Li et al. FNO (2020) Burgers experiments", "classic 1D viscous Burgers suites"],
    },
    {
        "param": "domain.t_final",
        "range": [0.5, 1.0],
        "rationale": (
            "Long enough for nonlinear steepening / weak shock formation while remaining "
            "stable under IMEX viscosity treatment."
        ),
        "refs": ["standard Burgers time horizons in NO literature"],
    },
    {
        "param": "viscosity.train",
        "range": [1e-3, 1e-2],
        "rationale": (
            "Covers moderate-Reynolds 1D regime: shocks form but dissipation prevents "
            "immediate blow-up of explicit schemes."
        ),
        "refs": ["viscous Burgers benchmark ranges"],
    },
    {
        "param": "viscosity.stress",
        "range": [3e-4, 5e-3],
        "rationale": (
            "Extended lower-ν envelope (Data_Management: train ≠ eval). Stresses residual "
            "and conservation when dissipation is weak."
        ),
        "refs": ["Data_Management.md extended envelope"],
    },
    {
        "param": "ic.n_modes",
        "range": [4, 4],
        "rationale": (
            "Low-mode sum-of-sines ICs — standard smooth initial data that develops "
            "nonlinear structure under Burgers dynamics."
        ),
        "refs": ["common FNO Burgers IC construction"],
    },
    {
        "param": "ic.coeff_bound_train",
        "range": [0.5, 0.5],
        "rationale": "Amplitude keeps solutions O(1) so relative L2 is meaningful.",
        "refs": [],
    },
    {
        "param": "ic.coeff_bound_stress",
        "range": [0.8, 0.8],
        "rationale": "Larger amplitude stress draw; extended envelope vs train.",
        "refs": ["Data_Management.md"],
    },
    {
        "param": "stress.shock_perturbation.steepen",
        "range": ["tanh(2.5 u)"],
        "rationale": (
            "Artificially steepens IC to accelerate shock formation — conservation and "
            "shock-capturing sensitivity without changing PDE."
        ),
        "refs": ["Trustless Verification §9.1 Burgers shock strength"],
    },
    {
        "param": "stress.high_freq_noise",
        "range": ["amp 0.02–0.08, modes 6–12"],
        "rationale": (
            "High-frequency IC perturbation (1D analogue of boundary-layer trip); "
            "tests robustness of learned operator to small-scale content."
        ),
        "refs": ["Trustless Verification §9.1 high-frequency perturbation"],
    },
]


def justification_table() -> Dict[str, Any]:
    return {
        "version": JUSTIFICATION_VERSION,
        "physics": "burgers1d",
        "parameters": BURGERS_PARAM_JUSTIFICATION,
    }

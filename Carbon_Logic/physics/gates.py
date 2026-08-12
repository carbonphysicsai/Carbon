"""Core physics gate evaluators for Hydrogen validators.

Hard gates return (passed: bool, details: dict). Score = 0 on any hard failure.
Phase 0 MVP: boundary, rollout_stability, uq_calibration. Mass/energy added for relevant PDEs.
"""

from typing import Dict, Tuple, Any
import numpy as np
import torch


def compute_relative_l2_error(pred: torch.Tensor, target: torch.Tensor) -> float:
    """Relative L2 error used in scoring."""
    diff = pred - target
    return float(torch.norm(diff) / (torch.norm(target) + 1e-12))


def boundary_satisfaction(
    u_pred: torch.Tensor, u_bc: torch.Tensor, threshold: float = 1e-3
) -> Tuple[bool, Dict[str, float]]:
    """Hard gate: Boundary condition satisfaction."""
    rel_error = compute_relative_l2_error(u_pred, u_bc)
    passed = rel_error < threshold
    return passed, {"relative_error": rel_error, "threshold": threshold}


def rollout_stability(
    energy_trajectory: torch.Tensor,
    threshold: float = 0.01,
    steps: int = 100,
) -> Tuple[bool, Dict[str, float]]:
    """Hard gate: Long-horizon rollout stability (no blow-up)."""
    if len(energy_trajectory) < steps:
        steps = len(energy_trajectory)
    e0 = energy_trajectory[0]
    eT = energy_trajectory[steps - 1]
    rel_drift = float(torch.abs(eT - e0) / (torch.abs(e0) + 1e-12))
    passed = rel_drift < threshold
    return passed, {"relative_drift": rel_drift, "threshold": threshold, "steps": steps}


def uq_calibration(
    coverage: float, target: float = 0.90, tolerance: float = 0.02
) -> Tuple[bool, Dict[str, float]]:
    """Hard gate: Uncertainty quantification calibration."""
    error = abs(coverage - target)
    passed = error < tolerance
    return passed, {"coverage_error": error, "target": target, "tolerance": tolerance}


def mass_conservation(
    div_u: torch.Tensor,
    u_norm: torch.Tensor,
    threshold: float = 1e-3,
) -> Tuple[bool, Dict[str, float]]:
    """Hard gate: Mass conservation (incompressible flow etc.). Relative L1."""
    rel_div = float(torch.norm(div_u, p=1) / (torch.norm(u_norm, p=1) + 1e-12))
    passed = rel_div < threshold
    return passed, {"relative_divergence": rel_div, "threshold": threshold}


def energy_dissipation(
    dE_dt: torch.Tensor,
    threshold: float = 1e-4,
) -> Tuple[bool, Dict[str, float]]:
    """Hard gate: Energy dissipation monotonicity / rate."""
    mean_diss = float(torch.mean(dE_dt)) if dE_dt.numel() > 0 else 0.0
    passed = mean_diss <= threshold
    return passed, {"mean_dissipation_rate": mean_diss, "threshold": threshold}


def evaluate_all_gates(
    results: Dict[str, Any], pde_type: str = "general"
) -> Tuple[bool, Dict[str, Any]]:
    """Run all relevant hard gates for a PDE type. Return overall pass + per-gate details."""
    details = {}
    overall_pass = True

    if "boundary_error" in results:
        passed, d = boundary_satisfaction(
            results.get("u_pred", torch.tensor(0.)),
            results.get("u_bc", torch.tensor(0.)),
            threshold=results.get("boundary_threshold", 1e-3),
        )
        details["boundary"] = {"passed": passed, **d}
        overall_pass &= passed

    if "energy_trajectory" in results:
        passed, d = rollout_stability(
            results["energy_trajectory"],
            threshold=results.get("rollout_threshold", 0.01),
        )
        details["rollout"] = {"passed": passed, **d}
        overall_pass &= passed

    if "uq_coverage" in results:
        passed, d = uq_calibration(
            results["uq_coverage"],
            target=results.get("uq_target", 0.90),
        )
        details["uq"] = {"passed": passed, **d}
        overall_pass &= passed

    if pde_type in ["ns", "burgers", "incompressible"] and "div_u" in results:
        passed, d = mass_conservation(results["div_u"], results.get("u_norm", torch.tensor(1.)))
        details["mass_conservation"] = {"passed": passed, **d}
        overall_pass &= passed

    if pde_type in ["ns", "burgers", "heat"] and "dE_dt" in results:
        passed, d = energy_dissipation(results["dE_dt"])
        details["energy_dissipation"] = {"passed": passed, **d}
        overall_pass &= passed

    details["overall_hard_pass"] = overall_pass
    return overall_pass, details

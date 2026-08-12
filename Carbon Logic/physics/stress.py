"""Deterministic stress testing utilities."""

import hashlib
import numpy as np
import torch

from .gates import evaluate_all_gates, compute_relative_l2_error


def _get_deterministic_rng(challenge_id: str, difficulty: float, salt: str = "hydrogen_stress_v1") -> np.random.Generator:
    """
    Create a fully deterministic numpy random generator based on challenge_id and difficulty.
    """
    seed_input = f"{challenge_id}:{difficulty:.6f}:{salt}".encode()
    seed = int(hashlib.sha256(seed_input).hexdigest(), 16) % (2**32)
    return np.random.default_rng(seed)


def generate_stress_conditions(
    challenge_id: str,
    backbone: str = "PINO",
    difficulty: float = 1.0,
    salt: str = "hydrogen_stress_v1",
) -> dict:
    rng = _get_deterministic_rng(challenge_id, difficulty, salt)

    conditions = {
        "challenge_id": challenge_id,
        "backbone": backbone,
        "difficulty": difficulty,
    }

    conditions["time_horizon_multiplier"] = 2.2 + difficulty * rng.uniform(1.0, 4.0)
    conditions["parameter_perturbation"] = rng.uniform(0.25, 0.9) * difficulty
    conditions["noise_level"] = rng.uniform(0.012, 0.08) * difficulty
    conditions["resolution_scale"] = rng.choice([1.0, 1.5, 2.0, 2.5, 3.0])

    if "ns_2d" in challenge_id or "navier" in challenge_id:
        conditions["reynolds_multiplier"] = 1.8 + rng.uniform(0.8, 3.2) * difficulty
        conditions["forcing_perturbation"] = rng.uniform(0.12, 0.45)
        conditions["divergence_tolerance"] = 3.5e-4 * (1 + difficulty * 1.0)
    elif "burgers" in challenge_id:
        conditions["viscosity_multiplier"] = rng.uniform(0.1, 5.0) * difficulty
    elif "darcy" in challenge_id:
        conditions["permeability_contrast"] = 180 + rng.uniform(80, 800) * difficulty
    elif "heat" in challenge_id:
        conditions["diffusivity_multiplier"] = rng.uniform(0.18, 4.5) * difficulty

    return conditions


def compute_divergence(u: torch.Tensor, v: torch.Tensor) -> torch.Tensor:
    du_dx = u[:, 1:] - u[:, :-1]
    dv_dy = v[1:, :] - v[:-1, :]
    du_dx = torch.nn.functional.pad(du_dx, (0, 1, 0, 0))
    dv_dy = torch.nn.functional.pad(dv_dy, (0, 0, 0, 1))
    return du_dx + dv_dy


def run_hard_gates(
    results: dict,
    pde_type: str,
    conditions: dict,
) -> tuple:
    hard_pass, gate_details = evaluate_all_gates(results, pde_type=pde_type)

    if not hard_pass:
        return False, gate_details

    difficulty = conditions.get("difficulty", 1.0)

    if pde_type == "navier_stokes":
        if "velocity" in results:
            vel = results["velocity"]
            if vel.dim() == 4 and vel.shape[1] >= 2:
                div = compute_divergence(vel[:, 0], vel[:, 1])
                if torch.max(torch.abs(div)) > conditions.get("divergence_tolerance", 3.5e-4):
                    gate_details["divergence_free"] = False
                    return False, gate_details

        if "energy_trajectory" in results:
            energy = results["energy_trajectory"]
            if len(energy) > 15:
                drift = abs(energy[-1] - energy[0]) / (abs(energy[0]) + 1e-8)
                if drift > 0.05 * difficulty:
                    gate_details["ns_long_term_stability"] = False
                    return False, gate_details

    if pde_type == "burgers":
        if "energy_trajectory" in results:
            energy = results["energy_trajectory"]
            if len(energy) > 12:
                if torch.any(energy < -0.02):
                    gate_details["burgers_negative_energy"] = False
                    return False, gate_details

    if "energy_trajectory" in results:
        energy = results["energy_trajectory"]
        if len(energy) > 16:
            drift = abs(energy[-1] - energy[0]) / (abs(energy[0]) + 1e-8)
            if drift > 0.08 * difficulty:
                gate_details["stress_rollout_stability"] = False
                return False, gate_details

    return True, gate_details


def compute_stress_metrics(
    u_pred: torch.Tensor,
    u_true: torch.Tensor,
    conditions: dict,
    pde_type: str,
    results: dict = None,
) -> dict:
    metrics = {}

    base_error = compute_relative_l2_error(u_pred, u_true).item()
    metrics["stress_l2_error"] = base_error

    param_pert = conditions.get("parameter_perturbation", 0.3)
    metrics["generalization_gap"] = base_error * (1 + param_pert * 2.0)
    metrics["ood_sensitivity"] = base_error * conditions.get("noise_level", 0.02) * 20

    difficulty = conditions.get("difficulty", 1.0)

    if pde_type == "navier_stokes":
        metrics["divergence_violation"] = base_error * 1.6 * difficulty
        metrics["long_term_dissipation"] = max(0.0, 1.0 - base_error * 6 * difficulty)
    elif pde_type == "burgers":
        metrics["shock_capturing_quality"] = max(0.0, 1.0 - base_error * 9)
        metrics["viscosity_robustness"] = max(0.0, 1.0 - base_error * 5.5 * difficulty)
    elif pde_type == "darcy":
        metrics["heterogeneous_robustness"] = max(0.0, 1.0 - base_error * 4)
    elif pde_type == "heat":
        metrics["diffusion_robustness"] = max(0.0, 1.0 - base_error * 4.5)

    if results is not None:
        uncertainty = results.get("uncertainty", results.get("std", results.get("ensemble_std", None)))
        if uncertainty is not None and isinstance(uncertainty, torch.Tensor):
            error_map = torch.abs(u_pred - u_true)
            if error_map.numel() > 10 and uncertainty.numel() > 10:
                err_flat = error_map.flatten().detach().cpu().numpy()
                unc_flat = uncertainty.flatten().detach().cpu().numpy()
                if np.std(unc_flat) > 1e-6:
                    corr = np.corrcoef(err_flat, unc_flat)[0, 1]
                    metrics["uq_error_correlation"] = float(corr)
                    metrics["uq_calibration_score"] = max(0.0, min(1.0, (corr + 1) / 2))

    return metrics


def run_stress_test(
    challenge_id: str,
    results: dict,
    u_pred: torch.Tensor,
    u_true: torch.Tensor,
    pde_type: str,
    difficulty: float = 1.0,
    salt: str = "hydrogen_stress_v1",
) -> dict:
    conditions = generate_stress_conditions(challenge_id, difficulty=difficulty, salt=salt)

    hard_pass, gate_details = run_hard_gates(results, pde_type, conditions)

    if not hard_pass:
        return {
            "hard_pass": False,
            "gate_details": gate_details,
            "stress_metrics": {},
            "final_stress_score": 0.0,
            "conditions": conditions,
        }

    stress_metrics = compute_stress_metrics(u_pred, u_true, conditions, pde_type, results=results)

    base_error = stress_metrics.get("stress_l2_error", 0.6)
    uq_calib = stress_metrics.get("uq_calibration_score", 0.5)

    final_stress_score = max(0.0, 1.0 - base_error * 3.2 + (uq_calib - 0.5) * 0.45)

    return {
        "hard_pass": True,
        "gate_details": gate_details,
        "stress_metrics": stress_metrics,
        "final_stress_score": final_stress_score,
        "conditions": conditions,
    }


def run_weak_local_stress_test(
    challenge_id: str,
    results: dict,
    u_pred: torch.Tensor,
    u_true: torch.Tensor,
    pde_type: str,
    difficulty: float = 0.45,
) -> dict:
    varied_difficulty = difficulty * (0.85 + np.random.default_rng(42).random() * 0.3)

    conditions = generate_stress_conditions(
        challenge_id, difficulty=varied_difficulty, salt="weak_local_stress"
    )

    hard_pass, gate_details = run_hard_gates(results, pde_type, conditions)

    if not hard_pass:
        return {
            "hard_pass": False,
            "gate_details": gate_details,
            "stress_metrics": {},
            "local_stress_score": 0.0,
            "conditions": conditions,
        }

    stress_metrics = compute_stress_metrics(u_pred, u_true, conditions, pde_type, results=results)

    base_error = stress_metrics.get("stress_l2_error", 0.6)
    local_stress_score = max(0.0, 1.0 - base_error * 2.8)

    return {
        "hard_pass": True,
        "gate_details": gate_details,
        "stress_metrics": stress_metrics,
        "local_stress_score": local_stress_score,
        "conditions": conditions,
    }

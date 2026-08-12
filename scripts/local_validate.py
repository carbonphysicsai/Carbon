"""Local Validation Script for carbon (Phase 0 MVP).

Run this to test the full data + gates pipeline before submitting to the subnet.

Simulates:
- Miner strategy JSON
- Dummy forward pass (placeholder for real PhysicsNeMo training)
- Hidden stress test + all hard physics gates
- Score calculation vs baseline
- Structured feedback (what agents/miners will see)

Usage:
    python scripts/local_validate.py --challenge poisson_2d_v1

This proves the gates and challenge loader work end-to-end.
"""

import argparse
import torch
import numpy as np
from carbon.challenges.poisson_2d import load_challenge, get_baseline_error
from carbon.physics.gates import evaluate_all_gates, compute_relative_l2_error


def dummy_forward_pass(
    challenge, strategy: dict
) -> Dict[str, torch.Tensor]:
    """Placeholder for real model training/inference.

    In real validator: load PhysicsNeMo PINO/FNO, apply strategy['pino']['loss_vector'],
    train on challenge.train_data, then predict on stress_data.

    For now: return slightly improved noisy version of ground truth + fake energy trajectory + UQ.
    """
    stress = challenge.stress_data
    u_true = stress["u_true"][0]  # take first sample

    # Simulate a "better" prediction (add small structured error that still passes gates)
    noise_level = strategy.get("noise_level", 0.015)
    u_pred = u_true + noise_level * torch.randn_like(u_true)

    # Fake divergence (very small for Poisson demo)
    div_u = 0.0005 * torch.randn_like(u_true)

    # Fake energy trajectory (stable for elliptic problem)
    T = 50
    energy = torch.linspace(1.0, 0.98, T) + 0.001 * torch.randn(T)

    # Fake UQ coverage (good calibration)
    uq_coverage = 0.91

    return {
        "u_pred": u_pred,
        "u_bc": u_true * 0.0,  # placeholder BC (dirichlet=0 on boundary for demo)
        "div_u": div_u,
        "u_norm": u_true,
        "energy_trajectory": energy,
        "uq_coverage": uq_coverage,
        "dE_dt": torch.tensor([-0.0002]),  # small dissipation
    }


def run_local_validation(challenge_id: str = "poisson_2d_v1", strategy_overrides: dict = None):
    """Full local dry-run."""
    print(f"\n=== carbon Local Validation ===")
    print(f"Challenge: {challenge_id}")

    challenge = load_challenge(challenge_id)
    print(f"Resolution: {challenge.resolution}")
    print(f"Current baseline relative L2: {challenge.baseline_error:.4f}")
    print(f"Symbolic priors: {challenge.symbolic_metadata['suggested_loss_weights']}")

    # Default strategy (miner would submit this)
    strategy = {
        "backbone": "PINO",
        "pino": {
            "loss_vector": challenge.symbolic_metadata["suggested_loss_weights"],
            "boundary_handling": "ghost_cells",
        },
        "noise_level": 0.012,  # controls how good the dummy prediction is
    }
    if strategy_overrides:
        strategy.update(strategy_overrides)

    print(f"\nStrategy: {strategy}")

    # Run dummy forward (replace with real training later)
    results = dummy_forward_pass(challenge, strategy)

    # Evaluate hard gates
    passed, gate_details = evaluate_all_gates(results, pde_type="poisson")
    print(f"\n--- Physics Gates ---")
    for gate, info in gate_details.items():
        status = "PASS" if info.get("passed", False) else "FAIL"
        print(f"  {gate}: {status}  details={info}")

    if not passed:
        print("\n*** HARD FAILURE *** Score = 0")
        return 0.0

    # Compute improvement
    u_pred = results["u_pred"]
    u_true = challenge.stress_data["u_true"][0]
    submission_error = compute_relative_l2_error(u_pred, u_true)
    improvement = np.log(challenge.baseline_error) - np.log(submission_error)

    print(f"\n--- Scoring ---")
    print(f"  Submission relative L2: {submission_error:.4f}")
    print(f"  Log-improvement vs baseline: {improvement:+.4f}")

    # Structured feedback (what the subnet will return to miner/agent)
    feedback = {
        "submission_id": "local_demo_001",
        "status": "accepted",
        "physics_gates": gate_details,
        "improvement_vs_baseline": round(improvement, 4),
        "suggestions": [],
        "causal_insights": [],  # Landscape will fill later
    }
    if improvement > 0.02:
        feedback["suggestions"].append("Good improvement. Consider increasing boundary weight slightly.")
    print(f"\n--- Structured Feedback (for miner/agent) ---")
    print(feedback)

    return improvement


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--challenge", default="poisson_2d_v1")
    parser.add_argument("--noise", type=float, default=0.012, help="Dummy prediction noise level")
    args = parser.parse_args()

    overrides = {"noise_level": args.noise}
    run_local_validation(args.challenge, overrides)

"""Navier-Stokes 2D with PDEBench support (highest priority for fluids)."""

from dataclasses import dataclass
from typing import Dict, Any, Tuple
import numpy as np
import torch

try:
    from hydrogen.data.pdebench_loader import PDEBenchLoader
    PDEBENCH_AVAILABLE = True
except ImportError:
    PDEBENCH_AVAILABLE = False


@dataclass
class Challenge:
    challenge_id: str
    problem: str
    dim: int
    resolution: Tuple[int, int]
    train_data: Dict[str, torch.Tensor]
    holdout_data: Dict[str, torch.Tensor]
    stress_data: Dict[str, torch.Tensor]
    symbolic_metadata: Dict[str, Any]
    baseline_error: float
    data_source: str = "synthetic"


def get_symbolic_metadata() -> Dict[str, Any]:
    return {
        "governing_pde": "∂u/∂t + (u·∇)u = -∇p + ν∇^{2}u,   ∇·u = 0",
        "symmetries": ["translation", "rotation", "galilean"],
        "conservation_laws": ["mass", "momentum"],
        "dimensionless_groups": {"Reynolds_number": "laminar"],
        "boundary_types": ["periodic", "no-slip"],
        "suggested_loss_weights": {
            "pde_residual": 1.0,
            "advection": 1.4,
            "viscous": 1.0,
            "pressure": 0.8,
            "divergence": 2.0,
            "boundary": 0.7,
        },
        "validity_domain": {"reynolds": [10, 200]},
        "hard_constraints": ["incompressible", "divergence_free"],
    }


def generate_ns_2d_data(...):  # keep existing synthetic version
    pass

def load_challenge(challenge_id: str = "ns_2d_laminar_v1", use_benchmark: bool = False) -> Challenge:
    if use_benchmark and PDEBENCH_AVAILABLE:
        try:
            loader = PDEBenchLoader(pde_name="ns_incom")
            raw_data = loader.load(max_samples=50)

            if "velocity_true" in raw_data:
                vel = raw_data["velocity_true"]
                n = vel.shape[0]
                s1, s2 = int(0.5 * n), int(0.75 * n)

                return Challenge(
                    challenge_id=challenge_id,
                    problem="navier_stokes",
                    dim=2,
                    resolution=(vel.shape[-2], vel.shape[-1]),
                    train_data={"velocity_true": vel[:s1]},
                    holdout_data={"velocity_true": vel[s1:s2]},
                    stress_data={"velocity_true": vel[s2:]},
                    symbolic_metadata=get_symbolic_metadata(),
                    baseline_error=loader.get_baseline_error(),
                    data_source="pdebench",
                )
        except Exception as e:
            print(f"[Warning] PDEBench NS load failed: {e}")

    # Synthetic fallback
    full_data = generate_ns_2d_data(n_samples=4)
    return Challenge(
        challenge_id=challenge_id,
        problem="navier_stokes",
        dim=2,
        resolution=(64, 64),
        train_data={k: v[:2] for k, v in full_data.items()},
        holdout_data={k: v[2:3] for k, v in full_data.items()},
        stress_data={k: v[3:4] for k, v in full_data.items()},
        symbolic_metadata=get_symbolic_metadata(),
        baseline_error=0.18,
        data_source="synthetic",
    )

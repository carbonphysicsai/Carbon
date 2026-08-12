"""Poisson 2D - Synthetic is sufficient and well-understood."""

from dataclasses import dataclass
from typing import Dict, Any, Tuple
import numpy as np
import torch


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


def get_symbolic_metadata_for_poisson() -> Dict[str, Any]:
    return {
        "governing_pde": "∇^{2}u = f",
        "symmetries": ["translation"],
        "conservation_laws": [],
        "boundary_types": ["dirichlet"],
        "suggested_loss_weights": {
            "pde_residual": 1.0,
            "boundary": 0.8,
        },
        "hard_constraints": ["elliptic"],
    }


def generate_poisson_data(
    resolution: Tuple[int, int] = (128, 128),
    seed: int = 42,
    n_samples: int = 8,
) -> Dict[str, torch.Tensor]:
    torch.manual_seed(seed)
    np.random.seed(seed)

    nx, ny = resolution
    x = torch.linspace(0, 1, nx)
    y = torch.linspace(0, 1, ny)
    X, Y = torch.meshgrid(x, y, indexing="ij")

    u_true = torch.sin(np.pi * X) * torch.sin(np.pi * Y)
    f = -2 * np.pi**2 * u_true
    u_noisy = u_true + 0.02 * torch.randn_like(u_true)

    return {
        "x": X.unsqueeze(0).repeat(n_samples, 1, 1),
        "y": Y.unsqueeze(0).repeat(n_samples, 1, 1),
        "u_true": u_true.unsqueeze(0).repeat(n_samples, 1, 1),
        "f": f.unsqueeze(0).repeat(n_samples, 1, 1),
        "u_noisy": u_noisy.unsqueeze(0).repeat(n_samples, 1, 1),
    }


def load_challenge(challenge_id: str = "poisson_2d_v1", use_benchmark: bool = False) -> Challenge:
    if use_benchmark:
        print("[Info] Poisson uses high-quality synthetic data (no strong benchmark needed).")

    full_data = generate_poisson_data(n_samples=8)
    return Challenge(
        challenge_id=challenge_id,
        problem="poisson",
        dim=2,
        resolution=(128, 128),
        train_data={k: v[:4] for k, v in full_data.items()},
        holdout_data={k: v[4:6] for k, v in full_data.items()},
        stress_data={k: v[6:8] for k, v in full_data.items()},
        symbolic_metadata=get_symbolic_metadata_for_poisson(),
        baseline_error=0.08,
        data_source="synthetic",
    )

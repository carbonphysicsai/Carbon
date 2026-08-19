"""Darcy 2D Challenge with PDEBench support."""

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
        "governing_pde": "-∇·(k ∇u) = f",
        "symmetries": ["translation"],
        "conservation_laws": [],
        "dimensionless_groups": {"permeability_contrast": "high"},
        "boundary_types": ["dirichlet"],
        "suggested_loss_weights": {
            "pde_residual": 1.2,
            "boundary": 0.7,
        },
        "validity_domain": {"permeability_contrast": [10, 1000]},
        "hard_constraints": ["elliptic"],
    }


def generate_darcy_data(
    resolution: Tuple[int, int] = (128, 128),
    seed: int = 42,
    n_samples: int = 8,
    permeability_contrast: float = 100.0,
) -> Dict[str, torch.Tensor]:
    torch.manual_seed(seed)
    np.random.seed(seed)

    nx, ny = resolution
    x = torch.linspace(0, 1, nx)
    y = torch.linspace(0, 1, ny)
    X, Y = torch.meshgrid(x, y, indexing="ij")

    k = 1.0 + permeability_contrast * torch.rand(nx, ny)
    u_true = torch.sin(np.pi * X) * torch.sin(np.pi * Y) * (1 + 0.1 * torch.sin(2 * np.pi * X * Y))
    f = torch.ones_like(u_true) * 0.1
    u_noisy = u_true + 0.03 * torch.randn_like(u_true)

    return {
        "x": X.unsqueeze(0).repeat(n_samples, 1, 1),
        "y": Y.unsqueeze(0).repeat(n_samples, 1, 1),
        "u_true": u_true.unsqueeze(0).repeat(n_samples, 1, 1),
        "f": f.unsqueeze(0).repeat(n_samples, 1, 1),
        "k": k.unsqueeze(0).repeat(n_samples, 1, 1),
        "u_noisy": u_noisy.unsqueeze(0).repeat(n_samples, 1, 1),
    }


def load_challenge(challenge_id: str = "darcy_2d_v1", use_benchmark: bool = False) -> Challenge:
    if use_benchmark and PDEBENCH_AVAILABLE:
        try:
            loader = PDEBenchLoader(pde_name="darcy")
            raw_data = loader.load(max_samples=200)

            # Convert PDEBench data into our expected format
            if "u_true" in raw_data:
                u_true = raw_data["u_true"]
                n = u_true.shape[0]
                split1, split2 = int(0.5 * n), int(0.75 * n)

                train_data = {"u_true": u_true[:split1]}
                holdout_data = {"u_true": u_true[split1:split2]}
                stress_data = {"u_true": u_true[split2:]}

                return Challenge(
                    challenge_id=challenge_id,
                    problem="darcy",
                    dim=2,
                    resolution=(u_true.shape[-2], u_true.shape[-1]),
                    train_data=train_data,
                    holdout_data=holdout_data,
                    stress_data=stress_data,
                    symbolic_metadata=get_symbolic_metadata(),
                    baseline_error=loader.get_baseline_error(),
                    data_source="pdebench",
                )
        except Exception as e:
            print(f"[Warning] Failed to load PDEBench data for Darcy: {e}. Falling back to synthetic.")

    # Synthetic fallback
    resolution = (128, 128)
    full_data = generate_darcy_data(resolution=resolution, n_samples=8)

    return Challenge(
        challenge_id=challenge_id,
        problem="darcy",
        dim=2,
        resolution=resolution,
        train_data={k: v[:4] for k, v in full_data.items()},
        holdout_data={k: v[4:6] for k, v in full_data.items()},
        stress_data={k: v[6:8] for k, v in full_data.items()},
        symbolic_metadata=get_symbolic_metadata(),
        baseline_error=0.095,
        data_source="synthetic",
    )

"""Burgers Challenge with benchmark support."""

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
        "governing_pde": "ρu/ρt + u·∇u = ν∇^{2}u",
        "symmetries": ["translation", "galilean"],
        "conservation_laws": ["momentum"],
        "dimensionless_groups": {"Reynolds_number": "moderate"},
        "boundary_types": ["periodic", "dirichlet"],
        "suggested_loss_weights": {
            "pde_residual": 1.0,
            "advection": 1.3,
            "diffusion": 0.8,
            "boundary": 0.6,
        },
        "validity_domain": {"viscosity": [0.001, 0.1]},
        "hard_constraints": ["nonlinear_advection"],
    }


def generate_burgers_data(
    resolution: Tuple[int, int] = (128, 64),
    seed: int = 42,
    n_samples: int = 6,
    viscosity: float = 0.01,
) -> Dict[str, torch.Tensor]:
    torch.manual_seed(seed)
    np.random.seed(seed)

    nx, nt = resolution
    x = torch.linspace(0, 1, nx)
    t = torch.linspace(0, 1, nt)
    X, T = torch.meshgrid(x, t, indexing="ij")

    u0 = torch.sin(2 * np.pi * x) + 0.1 * torch.sin(4 * np.pi * x)
    u = torch.zeros(nx, nt)
    u[:, 0] = u0

    dx = x[1] - x[0]
    dt = t[1] - t[0]

    for n in range(nt - 1):
        u_x = (torch.roll(u[:, n], -1) - torch.roll(u[:, n], 1)) / (2 * dx)
        u_xx = (torch.roll(u[:, n], -1) - 2 * u[:, n] + torch.roll(u[:, n], 1)) / dx**2
        u[:, n + 1] = u[:, n] - dt * u[:, n] * u_x + viscosity * dt * u_xx

    u_noisy = u + 0.02 * torch.randn_like(u)

    return {
        "x": X.unsqueeze(0).repeat(n_samples, 1, 1),
        "t": T.unsqueeze(0).repeat(n_samples, 1, 1),
        "u_true": u.unsqueeze(0).repeat(n_samples, 1, 1),
        "u_noisy": u_noisy.unsqueeze(0).repeat(n_samples, 1, 1),
        "viscosity": torch.full((n_samples, 1, 1), viscosity),
    }


def load_challenge(challenge_id: str = "burgers_v1", use_benchmark: bool = False) -> Challenge:
    if use_benchmark and PDEBENCH_AVAILABLE:
        try:
            loader = PDEBenchLoader(pde_name="burgers")
            raw_data = loader.load(max_samples=100)
            if "u_true" in raw_data:
                u_true = raw_data["u_true"]
                n = u_true.shape[0]
                s1, s2 = int(0.5 * n), int(0.75 * n)
                return Challenge(
                    challenge_id=challenge_id,
                    problem="burgers",
                    dim=1,
                    resolution=(u_true.shape[-2], u_true.shape[-1]),
                    train_data={"u_true": u_true[:s1]},
                    holdout_data={"u_true": u_true[s1:s2]},
                    stress_data={"u_true": u_true[s2:]},
                    symbolic_metadata=get_symbolic_metadata(),
                    baseline_error=loader.get_baseline_error(),
                    data_source="pdebench",
                )
        except Exception as e:
            print(f"[Warning] PDEBench failed for Burgers: {e}")

    # Synthetic fallback
    full_data = generate_burgers_data(n_samples=6)
    return Challenge(
        challenge_id=challenge_id,
        problem="burgers",
        dim=1,
        resolution=(128, 64),
        train_data={k: v[:3] for k, v in full_data.items()},
        holdout_data={k: v[3:4] for k, v in full_data.items()},
        stress_data={k: v[4:6] for k, v in full_data.items()},
        symbolic_metadata=get_symbolic_metadata(),
        baseline_error=0.12,
        data_source="synthetic",
    )

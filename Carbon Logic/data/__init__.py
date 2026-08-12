"""Unified data loading interface for Hydrogen.

All challenges should go through this for consistency.
"""

from typing import Optional
from .pdebench_loader import PDEBenchLoader
from .synthetic_loader import SyntheticLoader


def get_challenge_data(
    challenge_id: str,
    use_benchmark: bool = True,
    max_samples: Optional[int] = None,
):
    """
    Unified entry point for loading challenge data.

    Tries PDEBench first (when available), falls back to synthetic.
    """
    pde_name = None
    if "darcy" in challenge_id:
        pde_name = "darcy"
    elif "ns_2d" in challenge_id or "navier" in challenge_id:
        pde_name = "ns_incom"
    elif "burgers" in challenge_id:
        pde_name = "burgers"
    elif "heat" in challenge_id:
        pde_name = "heat"

    if use_benchmark and pde_name:
        try:
            loader = PDEBenchLoader(pde_name=pde_name)
            return loader.load(max_samples=max_samples)
        except Exception as e:
            print(f"[Data] PDEBench load failed for {challenge_id}: {e}. Using synthetic.")

    # Fallback
    from hydrogen.challenges import load_challenge
    challenge = load_challenge(challenge_id, use_benchmark=False)
    return challenge.stress_data  # or full data as needed

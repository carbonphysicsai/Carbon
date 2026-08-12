"""Synthetic data loader (fallback / for challenges without benchmark data)."""

from typing import Dict, Any
import torch


class SyntheticLoader:
    """Generates synthetic data on the fly (current implementation in each challenge file)."""

    def __init__(self):
        pass

    def load(self, **kwargs) -> Dict[str, torch.Tensor]:
        raise NotImplementedError("Use the per-challenge generate_*_data functions for now.")

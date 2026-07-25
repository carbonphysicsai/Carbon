# neurons/utils/determinism.py

"""
Centralized determinism utilities for Carbon.

Seed hierarchy is defined in carbon.common.seeds (SPEC §9):
  master = hash(challenge_id | block_hash | run_nonce)
  sub-streams via splitmix-style derivation.

This module provides framework-level determinism controls (PyTorch / JAX)
and thin wrappers that call the canonical seed functions.
"""

import os
from typing import Dict, Optional, Union

import torch

from carbon.common.seeds import (
    derive_master_seed,
    derive_pipeline_seeds,
    splitmix64,
)

# Back-compat re-exports
get_master_seed = derive_master_seed  # type: ignore[assignment]


def get_sub_seeds(master_seed: int) -> Dict[str, int]:
    """Alias for derive_pipeline_seeds (SPEC stream map)."""
    return derive_pipeline_seeds(master_seed)


def setup_pytorch_determinism(seed: int):
    torch.manual_seed(int(seed) % (2**32))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(seed) % (2**32))
    try:
        torch.use_deterministic_algorithms(True)
    except Exception:
        pass
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    os.environ["PYTHONHASHSEED"] = str(int(seed) % (2**32))
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")


def setup_jax_determinism(seed: int):
    """JAX path: threefry PRNG + env flags (SPEC / JAX_Optimization)."""
    os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    try:
        import jax

        jax.config.update("jax_default_prng_impl", "threefry")
        # Optional: enable stricter determinism when available
        try:
            jax.config.update("jax_enable_x64", False)
        except Exception:
            pass
        return jax.random.PRNGKey(int(seed) % (2**32))
    except ImportError:
        return None


def get_jax_key(master_seed: int):
    return setup_jax_determinism(master_seed)


def get_data_loader_generator(seed: int) -> torch.Generator:
    g = torch.Generator()
    g.manual_seed(int(seed) % (2**32))
    return g


def setup_determinism_for_component(
    component: str,
    master_seed: int,
    sub_seeds: Optional[Dict[str, int]] = None,
):
    if sub_seeds is None:
        sub_seeds = derive_pipeline_seeds(master_seed)

    seed = sub_seeds.get(component, master_seed)

    if component in [
        "data_loading",
        "augmentation",
        "training",
        "scoring",
        "data_seed",
        "init_seed",
    ]:
        setup_pytorch_determinism(seed)

    return seed


def master_seed_from_block(
    challenge_id: str,
    block_hash: str,
    run_nonce: Union[int, str] = 0,
) -> int:
    """Preferred validator entry point (SPEC)."""
    return derive_master_seed(challenge_id, block_hash, run_nonce)

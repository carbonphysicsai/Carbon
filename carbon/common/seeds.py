"""Seed hierarchy — canonical implementation of SPEC §9 / Data_Management.

master_seed = hash(challenge_id ‖ block_hash ‖ run_nonce)
  ├── data_seed    → training data (miner-influenced envelope allowed)
  ├── stress_seed  → hidden stress variants (validator-only; never to miners)
  ├── init_seed    → weight initialization
  ├── dropout_seed → dropout RNG
  └── shuffle_seed → train/val split

Invariant: stress_seed derivation path is distinct from data_seed and is
unknown to miners until evaluation (block_hash is not available pre-submit).
"""

from __future__ import annotations

import hashlib
from typing import Dict, Union


def _sha256_int(material: str) -> int:
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return int(digest, 16)


def derive_master_seed(
    challenge_id: str,
    block_hash: str,
    run_nonce: Union[int, str] = 0,
) -> int:
    """SPEC: hash(challenge_id + block_hash + run_nonce) → master seed.

    Returns a 63-bit positive int suitable for PRNG seeding across
    frameworks (fits safely in signed int64 and Python random).
    """
    material = f"{challenge_id}|{block_hash}|{run_nonce}"
    return _sha256_int(material) % (2**63 - 1)


def splitmix64(seed: int, stream: int) -> int:
    """Deterministic sub-stream derivation (SPEC splitmix-style)."""
    material = f"{seed}|stream:{stream}"
    return _sha256_int(material) % (2**63 - 1)


def derive_pipeline_seeds(master_seed: int) -> Dict[str, int]:
    """Derive all pipeline role seeds from a master seed.

    Stream indices are fixed constants — never reorder without a version bump.
    """
    return {
        "data_seed": splitmix64(master_seed, 0),
        "stress_seed": splitmix64(master_seed, 1),
        "init_seed": splitmix64(master_seed, 2),
        "dropout_seed": splitmix64(master_seed, 3),
        "shuffle_seed": splitmix64(master_seed, 4),
        # Aliases used by older call sites
        "training": splitmix64(master_seed, 0),
        "stress_generation": splitmix64(master_seed, 1),
        "scoring": splitmix64(master_seed, 5),
        "augmentation": splitmix64(master_seed, 6),
        "data_loading": splitmix64(master_seed, 0),
        "noise": splitmix64(master_seed, 7),
    }


def derive_role_seed(
    challenge_id: str,
    role: str,
    local_nonce: Union[int, str] = 0,
    run_id: str = "",
) -> int:
    """PoC / local-loop role seed (train | eval | stress).

    Used by miner local loops and the Burgers PoC. Validator official
    evaluation must use derive_master_seed + derive_pipeline_seeds with
    a real block_hash instead.
    """
    if role not in {"train", "eval", "stress"}:
        raise ValueError(f"role must be train|eval|stress, got {role!r}")
    material = f"{challenge_id}|{role}|{local_nonce}|{run_id}"
    return _sha256_int(material) % (2**63 - 1)

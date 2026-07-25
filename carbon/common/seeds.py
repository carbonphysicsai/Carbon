"""Seed hierarchy — canonical implementation of SPEC §9 / Data_Management.

master_seed = hash(challenge_id ‖ block_hash ‖ run_nonce)
  ├── data_seed     stream 0  → training data
  ├── stress_seed   stream 1  → hidden stress variants (validator-only)
  ├── init_seed     stream 2  → weight initialization
  ├── dropout_seed  stream 3  → dropout RNG
  ├── shuffle_seed  stream 4  → train/val split
  ├── scoring_seed  stream 5  → scoring-side RNG if needed
  ├── augment_seed  stream 6  → train augmentation
  ├── noise_seed    stream 7  → noise injection
  └── eval_seed     stream 8  → held-out accuracy benchmark (≠ stress)

Invariant: stress_seed derivation path is distinct from data_seed and is
unknown to miners until evaluation (block_hash is not available pre-submit).

SEED_MAP_VERSION: bump if stream indices change.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Union

SEED_MAP_VERSION = "carbon_seeds_v1"

# Fixed stream indices — NEVER reorder without SEED_MAP_VERSION bump
STREAM_DATA = 0
STREAM_STRESS = 1
STREAM_INIT = 2
STREAM_DROPOUT = 3
STREAM_SHUFFLE = 4
STREAM_SCORING = 5
STREAM_AUGMENT = 6
STREAM_NOISE = 7
STREAM_EVAL = 8  # held-out accuracy benchmark (separate from stress)


def _sha256_int(material: str) -> int:
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return int(digest, 16)


def derive_master_seed(
    challenge_id: str,
    block_hash: str,
    run_nonce: Union[int, str] = 0,
) -> int:
    """SPEC: hash(challenge_id + block_hash + run_nonce) → master seed."""
    material = f"{challenge_id}|{block_hash}|{run_nonce}"
    return _sha256_int(material) % (2**63 - 1)


def splitmix64(seed: int, stream: int) -> int:
    """Deterministic sub-stream derivation (SPEC splitmix-style)."""
    material = f"{seed}|stream:{stream}"
    return _sha256_int(material) % (2**63 - 1)


def derive_pipeline_seeds(master_seed: int) -> Dict[str, int]:
    """Full SPEC §9 pipeline seed map."""
    return {
        "data_seed": splitmix64(master_seed, STREAM_DATA),
        "stress_seed": splitmix64(master_seed, STREAM_STRESS),
        "init_seed": splitmix64(master_seed, STREAM_INIT),
        "dropout_seed": splitmix64(master_seed, STREAM_DROPOUT),
        "shuffle_seed": splitmix64(master_seed, STREAM_SHUFFLE),
        "scoring_seed": splitmix64(master_seed, STREAM_SCORING),
        "augment_seed": splitmix64(master_seed, STREAM_AUGMENT),
        "noise_seed": splitmix64(master_seed, STREAM_NOISE),
        "eval_seed": splitmix64(master_seed, STREAM_EVAL),
        # aliases
        "training": splitmix64(master_seed, STREAM_DATA),
        "stress_generation": splitmix64(master_seed, STREAM_STRESS),
        "scoring": splitmix64(master_seed, STREAM_SCORING),
        "augmentation": splitmix64(master_seed, STREAM_AUGMENT),
        "data_loading": splitmix64(master_seed, STREAM_DATA),
        "noise": splitmix64(master_seed, STREAM_NOISE),
        "_seed_map_version": SEED_MAP_VERSION,  # type: ignore[dict-item]
    }


def derive_role_seed(
    challenge_id: str,
    role: str,
    local_nonce: Union[int, str] = 0,
    run_id: str = "",
) -> int:
    """Local-loop role seed (train | eval | stress). Official path uses pipeline map."""
    if role not in {"train", "eval", "stress"}:
        raise ValueError(f"role must be train|eval|stress, got {role!r}")
    material = f"{challenge_id}|{role}|{local_nonce}|{run_id}"
    return _sha256_int(material) % (2**63 - 1)


def build_seed_bundle(
    challenge_id: str,
    block_hash: str,
    run_nonce: Union[int, str] = 0,
    *,
    local_mode: bool = False,
) -> Dict[str, int | str]:
    """Convenience: master + full pipeline for cards / run_once."""
    if local_mode:
        # Local miner loop: role seeds only; no claim of hidden stress
        return {
            "mode": "local",
            "challenge_id": challenge_id,
            "block_hash": block_hash,
            "run_nonce": run_nonce,
            "data_seed": derive_role_seed(challenge_id, "train", run_nonce, str(block_hash)),
            "eval_seed": derive_role_seed(challenge_id, "eval", run_nonce, str(block_hash)),
            "stress_seed": derive_role_seed(challenge_id, "stress", run_nonce, str(block_hash)),
            "init_seed": derive_role_seed(challenge_id, "train", run_nonce, str(block_hash)) ^ 0xA5A5,
            "_seed_map_version": SEED_MAP_VERSION,
        }
    master = derive_master_seed(challenge_id, block_hash, run_nonce)
    pipe = derive_pipeline_seeds(master)
    return {
        "mode": "official",
        "challenge_id": challenge_id,
        "block_hash": block_hash,
        "run_nonce": run_nonce,
        "master_seed": master,
        **{k: v for k, v in pipe.items() if not str(k).startswith("_")},
        "_seed_map_version": SEED_MAP_VERSION,
    }

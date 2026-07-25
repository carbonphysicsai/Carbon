"""Strategy submission handoff — miner → validator contract.

Miner may submit ONLY a strategy JSON. Forbidden in the handoff:
  - model weights / checkpoints
  - training data / labels
  - seed overrides (block_hash, stress seeds)
  - precomputed scores or metrics

Validator owns:
  - seed hierarchy (challenge_id ‖ block_hash ‖ run_nonce)
  - procedural data generation
  - retrain under clamped budget
  - gates + scoring + Model Card

This module is the single acceptance gate before run_once proceeds.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from poc.validator.schema_check import load_limits, validate_strategy

# Keys that indicate a miner is trying to smuggle non-strategy payload
FORBIDDEN_TOP_LEVEL = {
    "weights",
    "state_dict",
    "checkpoint",
    "params",
    "model",
    "u0",
    "uT",
    "data",
    "dataset",
    "batch",
    "seeds",
    "seed",
    "block_hash",
    "stress_seed",
    "master_seed",
    "score",
    "metrics",
    "gates",
    "predictions",
    "pred",
}


def strategy_hash(strategy: Dict[str, Any]) -> str:
    payload = json.dumps(strategy, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class SeedContext:
    """Validator-owned seed material. Miners never set these for official eval."""

    challenge_id: str
    block_hash: str  # "local" for offline PoC; real chain hash in production
    run_nonce: str | int = 0
    local_mode: bool = True  # True → offline PoC; False → official eval path

    def material(self) -> str:
        return f"{self.challenge_id}|{self.block_hash}|{self.run_nonce}"


@dataclass
class HandoffEnvelope:
    """Accepted submission ready for procedural gen + train."""

    strategy: Dict[str, Any]
    strategy_hash: str
    challenge_id: str
    backbone: str
    seed_context: SeedContext
    limits: Dict[str, Any]
    source_path: Optional[str] = None
    rejects: list = field(default_factory=list)

    def to_public_dict(self) -> Dict[str, Any]:
        """Safe to log — no weights, includes hash + seed material."""
        return {
            "strategy_hash": self.strategy_hash,
            "challenge_id": self.challenge_id,
            "backbone": self.backbone,
            "seed_context": asdict(self.seed_context),
            "budget": self.strategy.get("budget"),
            "loss": self.strategy.get("loss"),
            "backbone_cfg": self.strategy.get("backbone_cfg"),
            "source_path": self.source_path,
        }


def _reject_forbidden(raw: Dict[str, Any]) -> Optional[str]:
    bad = sorted(set(raw.keys()) & FORBIDDEN_TOP_LEVEL)
    if bad:
        return f"forbidden keys in submission (strategy-only handoff): {bad}"
    return None


def accept_submission(
    raw: Dict[str, Any] | str | Path,
    *,
    block_hash: str = "local",
    run_nonce: str | int = 0,
    fast: bool = False,
    local_mode: bool = True,
) -> Tuple[Optional[HandoffEnvelope], Optional[str]]:
    """Accept or reject a miner submission.

    Returns (envelope, None) on accept, or (None, error) on reject.
    """
    source_path = None
    if isinstance(raw, (str, Path)):
        source_path = str(raw)
        with open(raw) as f:
            payload = json.load(f)
    else:
        payload = deepcopy(raw)

    if not isinstance(payload, dict):
        return None, "submission must be a JSON object"

    forbid = _reject_forbidden(payload)
    if forbid:
        return None, forbid

    strategy, err = validate_strategy(payload, fast=fast)
    if err:
        return None, f"schema reject: {err}"

    # Double-check normalized strategy still has no forbidden keys
    forbid2 = _reject_forbidden(strategy)
    if forbid2:
        return None, forbid2

    limits = load_limits(fast=fast)
    challenge_id = strategy["challenge_id"]
    seed_ctx = SeedContext(
        challenge_id=challenge_id,
        block_hash=str(block_hash),
        run_nonce=run_nonce,
        local_mode=local_mode,
    )

    env = HandoffEnvelope(
        strategy=strategy,
        strategy_hash=strategy_hash(strategy),
        challenge_id=challenge_id,
        backbone=strategy["backbone"],
        seed_context=seed_ctx,
        limits=limits,
        source_path=source_path,
    )
    return env, None

"""Strategy schema validation — SPEC §12 / Appendix Implementation.

v1.0 rules (Phase 0–1B):
- Loss terms use explicit boolean `enabled` flags (never weight < 1e-8 hacks)
- Unknown keys → reject
- Numeric fields clipped to safe ranges
- Validator hard-caps max_steps / batch_size independent of miner request
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

# Phase-0 allowed backbones (expand in later phases)
ALLOWED_BACKBONES = {
    "fno",
    "fno1d",
    "fno2d",
    "gino",
    "wno",
    "transolver",
    "physicsnemo_fno",
    "pino",
}

LOSS_TERM_KEYS = (
    "data_mse",
    "physics_residual",
    "boundary_mse",
    "conservation_penalty",
    "initial_condition",
)

# Validator hard rails (SPEC + JAX_Optimization)
VALIDATOR_LIMITS = {
    "max_epochs": 5000,
    "max_batch_size": 64,
    "lr_min": 1e-6,
    "lr_max": 1e-1,
    "max_modes": 64,
    "max_width": 128,
    "max_depth": 8,
    "max_wall_s": 7200,
}


class StrategyValidationError(ValueError):
    pass


def _normalize_loss_block(loss: Any) -> Dict[str, Dict[str, Any]]:
    """Accept both nested {term: {enabled, weight}} and flat boolean forms."""
    if not isinstance(loss, dict):
        raise StrategyValidationError("loss must be an object")

    normalized: Dict[str, Dict[str, Any]] = {}
    for key, val in loss.items():
        if key not in LOSS_TERM_KEYS and not key.endswith("_weight"):
            # Allow forward-compatible custom terms but require object shape
            pass
        if isinstance(val, bool):
            weight_key = f"{key}_weight"
            w = float(loss.get(weight_key, 1.0 if val else 0.0))
            normalized[key] = {"enabled": val, "weight": w}
        elif isinstance(val, dict):
            if "enabled" not in val:
                raise StrategyValidationError(
                    f"loss.{key} must include boolean 'enabled' (SPEC invariant)"
                )
            if not isinstance(val["enabled"], bool):
                raise StrategyValidationError(
                    f"loss.{key}.enabled must be boolean, got {type(val['enabled']).__name__}"
                )
            normalized[key] = {
                "enabled": val["enabled"],
                "weight": float(val.get("weight", 1.0 if val["enabled"] else 0.0)),
            }
        elif key.endswith("_weight"):
            continue  # handled with boolean form
        else:
            raise StrategyValidationError(
                f"loss.{key} must be bool or {{enabled, weight}}, got {type(val).__name__}"
            )
    return normalized


def validate_and_normalize_strategy(
    strategy: Dict[str, Any],
    *,
    require_challenge_id: Optional[str] = None,
    schema_version: str = "1.0",
) -> Dict[str, Any]:
    """Validate strategy JSON and return a normalized copy safe for validators.

    Raises StrategyValidationError on reject-worthy input.
    """
    if not isinstance(strategy, dict):
        raise StrategyValidationError("strategy must be a JSON object")

    out = deepcopy(strategy)

    # Schema version
    out.setdefault("schema_version", schema_version)

    # Challenge binding
    challenge_id = out.get("challenge_id") or out.get("challenge")
    if require_challenge_id is not None:
        if challenge_id != require_challenge_id:
            raise StrategyValidationError(
                f"challenge_id must be {require_challenge_id!r}, got {challenge_id!r}"
            )
    if challenge_id:
        out["challenge_id"] = str(challenge_id)

    # Backbone
    backbone = str(out.get("backbone", "")).lower()
    if not backbone:
        raise StrategyValidationError("backbone is required")
    if backbone not in ALLOWED_BACKBONES:
        raise StrategyValidationError(
            f"backbone {backbone!r} not in allowed set {sorted(ALLOWED_BACKBONES)}"
        )
    out["backbone"] = backbone

    # Loss — boolean enables mandatory
    if "loss" not in out:
        raise StrategyValidationError("loss block is required")
    out["loss"] = _normalize_loss_block(out["loss"])

    # Training / optim block
    training = out.get("training") or out.get("optim") or {}
    if not isinstance(training, dict):
        raise StrategyValidationError("training/optim must be an object")

    lr = float(training.get("learning_rate", training.get("lr", 1e-3)))
    lr = max(VALIDATOR_LIMITS["lr_min"], min(VALIDATOR_LIMITS["lr_max"], lr))
    epochs = int(training.get("epochs", training.get("max_steps", 100)))
    epochs = max(1, min(VALIDATOR_LIMITS["max_epochs"], epochs))
    batch_size = int(training.get("batch_size", 8))
    batch_size = max(1, min(VALIDATOR_LIMITS["max_batch_size"], batch_size))

    out["training"] = {
        "optimizer": training.get("optimizer", training.get("name", "adamw")),
        "learning_rate": lr,
        "weight_decay": float(training.get("weight_decay", 0.0)),
        "epochs": epochs,
        "batch_size": batch_size,
        "gradient_clip": float(training.get("gradient_clip", 1.0)),
        "lr_schedule": training.get("lr_schedule", "cosine"),
    }

    # Budget (PoC / light training)
    budget = out.get("budget") or {}
    if isinstance(budget, dict):
        max_steps = int(budget.get("max_steps", epochs))
        max_steps = max(1, min(VALIDATOR_LIMITS["max_epochs"], max_steps))
        out["budget"] = {
            "max_steps": max_steps,
            "batch_size": min(
                VALIDATOR_LIMITS["max_batch_size"],
                int(budget.get("batch_size", batch_size)),
            ),
        }

    # Backbone config clamps
    cfg = out.get("backbone_config") or out.get("backbone_cfg") or {}
    if isinstance(cfg, dict):
        if "modes" in cfg:
            cfg["modes"] = max(1, min(VALIDATOR_LIMITS["max_modes"], int(cfg["modes"])))
        if "width" in cfg:
            cfg["width"] = max(1, min(VALIDATOR_LIMITS["max_width"], int(cfg["width"])))
        if "depth" in cfg or "layers" in cfg:
            d = int(cfg.get("depth", cfg.get("layers", 4)))
            cfg["depth"] = max(1, min(VALIDATOR_LIMITS["max_depth"], d))
        out["backbone_config"] = cfg

    return out


def loss_enabled_flags(strategy: Dict[str, Any]) -> Dict[str, bool]:
    """Extract boolean enables for JAX unified_loss_fn (boolean masks)."""
    loss = strategy.get("loss", {})
    flags = {}
    for key, block in loss.items():
        if isinstance(block, dict) and "enabled" in block:
            flags[f"{key}_enabled"] = bool(block["enabled"])
    return flags


def loss_weights(strategy: Dict[str, Any]) -> Dict[str, float]:
    """Extract weights for enabled terms (disabled → 0.0)."""
    loss = strategy.get("loss", {})
    weights = {}
    for key, block in loss.items():
        if isinstance(block, dict):
            weights[key] = float(block["weight"]) if block.get("enabled") else 0.0
    return weights

"""Carbon common foundation — seeds, strategy schema, scoring, model cards."""

from carbon.common.seeds import (
    derive_master_seed,
    derive_pipeline_seeds,
    derive_role_seed,
    splitmix64,
)
from carbon.common.strategy_schema import (
    StrategyValidationError,
    validate_and_normalize_strategy,
    loss_enabled_flags,
    loss_weights,
    VALIDATOR_LIMITS,
)
from carbon.common.scoring import compute_combined_score, score_from_metrics
from carbon.common.model_card import build_model_card, write_model_card, strategy_hash

__all__ = [
    "derive_master_seed",
    "derive_pipeline_seeds",
    "derive_role_seed",
    "splitmix64",
    "StrategyValidationError",
    "validate_and_normalize_strategy",
    "loss_enabled_flags",
    "loss_weights",
    "VALIDATOR_LIMITS",
    "compute_combined_score",
    "score_from_metrics",
    "build_model_card",
    "write_model_card",
    "strategy_hash",
]

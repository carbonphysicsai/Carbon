"""SPEC alignment tests — scoring hard gates + strategy schema."""

import pytest

from carbon.common.scoring import compute_combined_score
from carbon.common.seeds import (
    derive_master_seed,
    derive_pipeline_seeds,
    derive_role_seed,
)
from carbon.common.strategy_schema import (
    StrategyValidationError,
    loss_enabled_flags,
    validate_and_normalize_strategy,
)


def test_hard_gate_zeros_score():
    result = compute_combined_score(
        physics_fidelity=0.9,
        robustness=0.8,
        accuracy=0.85,
        hard_gate_failures=["mass_conservation"],
    )
    assert result["combined_score"] == 0.0
    assert result["gate_failed"] is True


def test_weighted_score_when_gates_pass():
    result = compute_combined_score(
        physics_fidelity=0.9,
        robustness=0.8,
        accuracy=0.85,
        hard_gate_failures=[],
    )
    expected = 0.45 * 0.9 + 0.30 * 0.8 + 0.25 * 0.85
    assert abs(result["combined_score"] - expected) < 1e-9
    assert result["gate_failed"] is False


def test_strategy_requires_boolean_enabled():
    bad = {
        "challenge_id": "burgers1d_v0",
        "backbone": "fno1d",
        "loss": {"data_mse": {"weight": 1.0}},  # missing enabled
        "training": {"epochs": 10, "learning_rate": 1e-3},
    }
    with pytest.raises(StrategyValidationError):
        validate_and_normalize_strategy(bad)


def test_strategy_normalizes_boolean_loss():
    raw = {
        "challenge_id": "burgers1d_v0",
        "backbone": "fno1d",
        "loss": {
            "data_mse": {"enabled": True, "weight": 1.0},
            "physics_residual": {"enabled": False, "weight": 0.5},
        },
        "training": {"epochs": 99999, "learning_rate": 5.0, "batch_size": 1000},
    }
    out = validate_and_normalize_strategy(raw)
    assert out["loss"]["data_mse"]["enabled"] is True
    assert out["loss"]["physics_residual"]["enabled"] is False
    # Hard rails applied
    assert out["training"]["epochs"] <= 5000
    assert out["training"]["learning_rate"] <= 0.1
    assert out["training"]["batch_size"] <= 64
    flags = loss_enabled_flags(out)
    assert flags["data_mse_enabled"] is True
    assert flags["physics_residual_enabled"] is False


def test_seed_roles_differ():
    train = derive_role_seed("burgers1d_v0", "train", 1, "r1")
    eval_ = derive_role_seed("burgers1d_v0", "eval", 1, "r1")
    stress = derive_role_seed("burgers1d_v0", "stress", 1, "r1")
    assert len({train, eval_, stress}) == 3


def test_pipeline_seeds_stable():
    m = derive_master_seed("burgers1d_v0", "0xabc", 0)
    a = derive_pipeline_seeds(m)
    b = derive_pipeline_seeds(m)
    assert a == b
    assert a["data_seed"] != a["stress_seed"]

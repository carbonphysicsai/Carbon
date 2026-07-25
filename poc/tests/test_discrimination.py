"""Strategy discrimination — locked behavioral contracts.

These tests are the de-risk bar for incentive integrity:
  - broken → combined == 0 (loss_signal / gates)
  - data_only and physics complete a full card
  - with JAX: if train_quality claims, must beat null and eval_rel_l2 < 0.5

Ranking physics ≥ data_only on stress is asserted only when both claim
train quality (otherwise protocol-only runs skip the soft rank check).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from poc.validator.run_once import run_once
from poc.train.loop import JAX_AVAILABLE

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "poc" / "fixtures"


def test_broken_zeros(tmp_path):
    card = run_once(
        str(FIXTURES / "strategy_broken.json"),
        local_nonce=42,
        run_id="disc_broken",
        artifacts_dir=tmp_path,
        fast=True,
    )
    assert card["score"]["gate_failed"] is True
    assert card["score"]["combined"] == 0.0
    assert "loss_signal" in card["score"]["hard_gate_failures"]


def test_data_only_completes(tmp_path):
    card = run_once(
        str(FIXTURES / "strategy_data_only.json"),
        local_nonce=42,
        run_id="disc_data",
        artifacts_dir=tmp_path,
        fast=True,
    )
    assert "score" in card
    assert "metrics" in card
    assert "null_rel_l2" in card["metrics"]
    assert card["budget_used"]["backend"] in ("jax", "numpy_fd")
    # null baseline always recorded
    assert card["metrics"]["null_rel_l2"] >= 0.0


def test_physics_completes(tmp_path):
    card = run_once(
        str(FIXTURES / "strategy_physics.json"),
        local_nonce=42,
        run_id="disc_phys",
        artifacts_dir=tmp_path,
        fast=True,
    )
    assert "score" in card
    assert card["metrics"]["precision"] == "fp32"


def test_train_quality_requires_null_and_l2(tmp_path):
    """If claim is True, all hard conditions must hold."""
    card = run_once(
        str(FIXTURES / "strategy_data_only.json"),
        local_nonce=7,
        run_id="disc_tq",
        artifacts_dir=tmp_path,
        fast=True,
    )
    tq = card["extra"]["train_quality"]
    if tq["train_quality_claim"]:
        assert card["budget_used"]["backend"] == "jax"
        assert card["metrics"]["eval_rel_l2"] < 0.50
        assert card["metrics"]["eval_rel_l2"] < card["metrics"]["null_rel_l2"]
    else:
        # reasons must be explicit — never silent false
        assert isinstance(tq["reasons"], list)


@pytest.mark.skipif(not JAX_AVAILABLE, reason="JAX required for rank assertion")
def test_physics_not_worse_than_data_when_both_learn(tmp_path):
    """Soft rank: when both strategies claim quality, physics stress ≤ data stress."""
    data = run_once(
        str(FIXTURES / "strategy_data_only.json"),
        local_nonce=11,
        run_id="rank_data",
        artifacts_dir=tmp_path / "d",
        fast=True,
    )
    phys = run_once(
        str(FIXTURES / "strategy_physics.json"),
        local_nonce=11,
        run_id="rank_phys",
        artifacts_dir=tmp_path / "p",
        fast=True,
    )
    if (
        data["extra"]["train_quality"]["train_quality_claim"]
        and phys["extra"]["train_quality"]["train_quality_claim"]
    ):
        assert phys["metrics"]["stress_rel_l2"] <= data["metrics"]["stress_rel_l2"] * 1.05

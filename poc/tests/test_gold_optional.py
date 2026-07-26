"""Gold budget path — real train-quality surface (skip in default CI)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from poc.validator.run_once import run_once
from poc.train.loop import JAX_AVAILABLE

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "poc" / "fixtures"

pytestmark = pytest.mark.skipif(
    os.environ.get("POC_GOLD", "0") != "1",
    reason="Set POC_GOLD=1 for gold-budget train-quality run",
)


def test_gold_fixture_runs(tmp_path):
    card = run_once(
        str(FIXTURES / "strategy_gold.json"),
        local_nonce=42,
        run_id="gold",
        artifacts_dir=tmp_path,
        fast=False,
    )
    assert card["budget_used"]["steps"] >= 1
    assert "null_rel_l2" in card["metrics"]
    assert card["extra"]["train_quality"] is not None
    # If JAX present, gold is the surface where claim *may* go true
    if JAX_AVAILABLE:
        assert card["budget_used"]["backend"] == "jax"
        # Do not force claim true (hardware/budget dependent) — force honesty
        reasons = card["extra"]["train_quality"]["reasons"]
        claim = card["extra"]["train_quality"]["train_quality_claim"]
        if claim:
            assert card["metrics"]["eval_rel_l2"] < 0.50
            assert card["metrics"]["eval_rel_l2"] < card["metrics"]["null_rel_l2"]
        else:
            assert isinstance(reasons, list)

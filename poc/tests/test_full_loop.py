"""T3 full loop, T4 gate fail, T7 budget cap."""

import json
from pathlib import Path

from poc.validator.run_once import run_once
from poc.validator.schema_check import validate_strategy

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "poc" / "fixtures"


def test_full_loop_writes_card(tmp_path):
    card = run_once(
        str(FIXTURES / "strategy_data_only.json"),
        local_nonce=11,
        run_id="t3",
        artifacts_dir=tmp_path,
        fast=True,
    )
    assert "card_id" in card
    assert card["challenge_id"] == "burgers1d_v0"
    assert card["backbone"] == "fno1d"
    assert "score" in card
    assert "gates" in card
    assert "seeds" in card
    assert (tmp_path / f"{card['card_id']}.json").exists()


def test_broken_strategy_gate_zeros(tmp_path):
    """T4: all-loss-disabled + tiny model must fail hard gates → combined=0."""
    card = run_once(
        str(FIXTURES / "strategy_broken.json"),
        local_nonce=12,
        run_id="t4",
        artifacts_dir=tmp_path,
        fast=True,
    )
    assert (tmp_path / f"{card['card_id']}.json").exists()
    assert card["score"]["gate_failed"] is True
    assert card["score"]["combined"] == 0.0
    assert len(card["score"]["hard_gate_failures"]) >= 1
    assert "loss_signal" in card["score"]["hard_gate_failures"]


def test_budget_cap_applied():
    raw = json.loads((FIXTURES / "strategy_physics.json").read_text())
    raw["budget"]["max_steps"] = 999999
    s, err = validate_strategy(raw, fast=True)
    assert err is None
    assert s["budget"]["max_steps"] <= 100

"""T1 — Schema reject."""

import json
from pathlib import Path

from poc.validator.schema_check import validate_strategy

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "poc" / "fixtures"


def test_valid_physics_strategy():
    raw = json.loads((FIXTURES / "strategy_physics.json").read_text())
    s, err = validate_strategy(raw, fast=True)
    assert err is None
    assert s["backbone"] == "fno1d"


def test_reject_wrong_backbone():
    raw = json.loads((FIXTURES / "strategy_physics.json").read_text())
    raw["backbone"] = "gino"
    s, err = validate_strategy(raw)
    assert s is None
    assert "backbone" in err


def test_reject_unknown_key():
    raw = json.loads((FIXTURES / "strategy_physics.json").read_text())
    raw["evil"] = 1
    s, err = validate_strategy(raw)
    assert s is None
    assert "unknown" in err


def test_budget_cap():
    raw = json.loads((FIXTURES / "strategy_physics.json").read_text())
    raw["budget"]["max_steps"] = 10_000_000
    s, err = validate_strategy(raw, fast=True)
    assert err is None
    assert s["budget"]["max_steps"] <= 50  # fast profile cap

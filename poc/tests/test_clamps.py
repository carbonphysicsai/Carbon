"""Validator hard clamps — miners cannot exceed limits."""

from copy import deepcopy
import json
from pathlib import Path

from poc.validator.schema_check import validate_strategy, load_limits
from poc.validator.handoff import accept_submission

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "poc" / "fixtures"


def _base():
    return json.loads((FIXTURES / "strategy_data_only.json").read_text())


def test_max_steps_clamped_fast():
    raw = _base()
    raw["budget"]["max_steps"] = 10**9
    s, err = validate_strategy(raw, fast=True)
    assert err is None
    limits = load_limits(fast=True)
    assert s["budget"]["max_steps"] == limits["max_steps"]
    assert s["budget"]["max_steps"] <= 100


def test_max_steps_clamped_full():
    raw = _base()
    raw["budget"]["max_steps"] = 10**9
    s, err = validate_strategy(raw, fast=False)
    assert err is None
    assert s["budget"]["max_steps"] == 5000


def test_batch_size_clamped():
    raw = _base()
    raw["budget"]["batch_size"] = 9999
    s, err = validate_strategy(raw, fast=True)
    assert err is None
    assert s["budget"]["batch_size"] <= load_limits(fast=True)["max_batch_size"]


def test_lr_clamped():
    raw = _base()
    raw["optim"]["lr"] = 50.0
    s, err = validate_strategy(raw, fast=True)
    assert err is None
    assert s["optim"]["lr"] <= load_limits(fast=True)["lr_max"]

    raw2 = _base()
    raw2["optim"]["lr"] = 1e-12
    s2, err2 = validate_strategy(raw2, fast=True)
    assert err2 is None
    assert s2["optim"]["lr"] >= load_limits(fast=True)["lr_min"]


def test_backbone_clamped():
    raw = _base()
    raw["backbone_cfg"]["modes"] = 999
    raw["backbone_cfg"]["width"] = 999
    raw["backbone_cfg"]["layers"] = 999
    s, err = validate_strategy(raw, fast=False)
    assert err is None
    lim = load_limits(fast=False)
    assert s["backbone_cfg"]["modes"] == lim["max_modes"]
    assert s["backbone_cfg"]["width"] == lim["max_width"]
    assert s["backbone_cfg"]["layers"] == lim["max_layers"]


def test_handoff_records_clamped_budget():
    raw = _base()
    raw["budget"]["max_steps"] = 10**6
    env, err = accept_submission(raw, fast=True)
    assert err is None
    assert env.strategy["budget"]["max_steps"] <= 100

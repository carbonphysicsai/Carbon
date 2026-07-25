"""Handoff + procedural seed tests."""

import json
from pathlib import Path

from poc.validator.handoff import accept_submission, FORBIDDEN_TOP_LEVEL
from poc.generators.burgers1d import generate_batch

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "poc" / "fixtures"


def test_accept_clean_strategy():
    env, err = accept_submission(FIXTURES / "strategy_data_only.json", fast=True)
    assert err is None
    assert env is not None
    assert env.strategy_hash.startswith("sha256:")
    assert env.backbone == "fno1d"
    assert env.seed_context.local_mode is True


def test_reject_weights_smuggle():
    raw = json.loads((FIXTURES / "strategy_data_only.json").read_text())
    raw["weights"] = [1, 2, 3]
    env, err = accept_submission(raw, fast=True)
    assert env is None
    assert "forbidden" in err
    assert "weights" in err


def test_reject_seed_smuggle():
    raw = json.loads((FIXTURES / "strategy_data_only.json").read_text())
    raw["block_hash"] = "0xdead"
    raw["stress_seed"] = 123
    env, err = accept_submission(raw, fast=True)
    assert env is None
    assert "forbidden" in err


def test_reject_data_smuggle():
    raw = json.loads((FIXTURES / "strategy_data_only.json").read_text())
    raw["uT"] = [[0.0]]
    env, err = accept_submission(raw, fast=True)
    assert env is None
    assert "forbidden" in err


def test_role_seeds_distinct_local():
    t = generate_batch("train", 1, "h1", fast=True, local_mode=True)
    e = generate_batch("eval", 1, "h1", fast=True, local_mode=True)
    s = generate_batch("stress", 1, "h1", fast=True, local_mode=True)
    assert len({t.seed, e.seed, s.seed}) == 3
    t.assert_finite()
    e.assert_finite()
    s.assert_finite()


def test_official_seeds_depend_on_block_hash():
    a = generate_batch(
        "train", 0, "off", fast=True, block_hash="0xaaa", local_mode=False
    )
    b = generate_batch(
        "train", 0, "off", fast=True, block_hash="0xbbb", local_mode=False
    )
    assert a.seed != b.seed
    assert a.provenance["mode"] == "official"
    assert "master_seed" in a.provenance


def test_same_inputs_reproducible():
    a = generate_batch("eval", 99, "repro", fast=True, local_mode=True)
    b = generate_batch("eval", 99, "repro", fast=True, local_mode=True)
    assert a.seed == b.seed
    assert a.hash() == b.hash()


def test_forbidden_set_covers_attack_surface():
    needed = {"weights", "checkpoint", "block_hash", "stress_seed", "uT", "score"}
    assert needed <= FORBIDDEN_TOP_LEVEL

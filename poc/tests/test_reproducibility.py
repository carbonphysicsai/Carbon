"""Reproducibility and security-boundary property tests."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from poc.validator.run_once import run_once
from poc.validator.handoff import accept_submission
from poc.generators.stress_categories import generate_stress_suite
from poc.generators.label_checks import check_label_conservation
from poc.generators.burgers1d import generate_batch
from carbon.common.seeds import build_seed_bundle

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "poc" / "fixtures"


def test_dual_run_identical_seeds_and_hashes(tmp_path):
    """Same inputs → same strategy_hash, seed bundle, payload hashes."""
    kwargs = dict(
        local_nonce=99,
        run_id="repro",
        fast=True,
        block_hash="0xrepro",
        local_mode=True,
    )
    a = run_once(
        str(FIXTURES / "strategy_data_only.json"),
        artifacts_dir=tmp_path / "a",
        **kwargs,
    )
    b = run_once(
        str(FIXTURES / "strategy_data_only.json"),
        artifacts_dir=tmp_path / "b",
        **kwargs,
    )
    assert a["extra"]["strategy_hash"] == b["extra"]["strategy_hash"]
    assert a["seeds"]["train_hash"] == b["seeds"]["train_hash"]
    assert a["seeds"]["eval_hash"] == b["seeds"]["eval_hash"]
    assert a["seeds"]["stress_payload_hashes"] == b["seeds"]["stress_payload_hashes"]
    assert a["seeds"]["init_seed"] == b["seeds"]["init_seed"]
    assert abs(a["score"]["combined"] - b["score"]["combined"]) < 1e-5


def test_strategy_mutation_does_not_change_stress_hashes():
    """Miner strategy fields must not move validator stress payloads."""
    stress_seed = int(
        build_seed_bundle("burgers1d_v0", "0xiso", 1, local_mode=False)["stress_seed"]
    )
    suite_a = generate_stress_suite(stress_seed, fast=True)

    raw = json.loads((FIXTURES / "strategy_data_only.json").read_text())
    raw2 = deepcopy(raw)
    raw2["optim"]["lr"] = 0.009
    raw2["backbone_cfg"]["width"] = 16
    raw2["budget"]["max_steps"] = 50
    env1, e1 = accept_submission(raw, fast=True, block_hash="0xiso", run_nonce=1)
    env2, e2 = accept_submission(raw2, fast=True, block_hash="0xiso", run_nonce=1)
    assert e1 is None and e2 is None
    assert env1.strategy_hash != env2.strategy_hash
    suite_b = generate_stress_suite(stress_seed, fast=True)
    assert suite_a.meta["payload_hashes"] == suite_b.meta["payload_hashes"]


def test_label_mass_conservation_train_eval():
    train = generate_batch("train", 5, "lab", fast=True)
    eval_b = generate_batch("eval", 5, "lab", fast=True)
    ok_t, info_t = check_label_conservation(train)
    ok_e, info_e = check_label_conservation(eval_b)
    assert ok_t, info_t
    assert ok_e, info_e


def test_broken_never_claims_train_quality(tmp_path):
    card = run_once(
        str(FIXTURES / "strategy_broken.json"),
        local_nonce=3,
        run_id="null_brk",
        artifacts_dir=tmp_path,
        fast=True,
    )
    assert card["extra"]["train_quality"]["train_quality_claim"] is False

"""Toy-only checks for the prospective duplicate-policy study."""

import copy
import json
from pathlib import Path

import pytest

from scripts.dev.incentive_policy_options import (
    POLICIES,
    SCENARIOS,
    Submission,
    _credit_shares,
    _eligible,
    _submissions,
    episode,
    main,
    simulate,
    validate,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/development/incentive-policy-options/assumptions.v1.json"


def fixture_config():
    cfg = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = cfg["base_simulation"]
    base.update(
        margins=[base["registered_equivalence_margin_rel"]],
        decays=[0.5],
        horizon_windows=8,
        exposure_limit=2,
        windows_per_decay_period=3,
        timing_arrival_window=2,
        comparison_windows=[1],
    )
    cfg["comparison_windows"] = 1
    cfg["replicates"] = 3
    return cfg


def test_exact_rebuild_digest_removes_extra_screening_attempts():
    cfg = fixture_config()
    base = cfg["base_simulation"] | cfg
    initial = Submission("initial", "initial", "initial", 0.074, -1.0, -1)
    items = _submissions("exact_four", base)
    assert len(items) == 5
    assert len(_eligible(items, initial, "hotkey", base)[0]) == 5
    assert len(_eligible(items, initial, "digest_split", base)[0]) == 2
    assert len(_eligible(items, initial, "digest_first", base)[0]) == 2


def test_near_rule_can_merge_a_distinct_better_artifact():
    cfg = fixture_config()
    base = cfg["base_simulation"] | cfg
    initial = Submission("initial", "initial", "initial", 0.074, -1.0, -1)
    near = _submissions("near_four", base)
    tight, tight_false = _eligible(near, initial, "near_first_tight", base)
    wide, wide_false = _eligible(near, initial, "near_first_wide", base)
    assert any(item.artifact == "best" for item in tight)
    assert not any(item.artifact == "best" for item in wide)
    assert tight_false == 0
    assert wide_false >= 1


def test_digest_split_caps_total_but_can_share_with_a_copier():
    cfg = fixture_config()
    best = _submissions("copy_best_honest_first", cfg["base_simulation"] | cfg)
    credit = _credit_shares("digest_split", best[0], {"best": best})
    assert credit == {"honest": 0.5, "attacker": 0.5}
    assert sum(credit.values()) == 1
    assert _credit_shares("digest_first", best[0], {"best": best}) == {"honest": 1.0}
    front_run = _submissions("copy_best_attacker_first", cfg["base_simulation"] | cfg)
    assert _credit_shares("digest_first", front_run[0], {"best": front_run}) == {
        "attacker": 1.0
    }


def test_replay_and_common_one_key_counterfactual():
    cfg = fixture_config()
    noise = {"median_within_recipe_sd": 0.002}
    rows = simulate(cfg, noise)
    assert rows == simulate(cfg, noise)
    assert len(rows) == len(SCENARIOS) * len(POLICIES)
    by_key = {(row["scenario"], row["policy"]): row for row in rows}
    assert by_key[("exact_four", "digest_first")]["sybil_gain_vs_one_key"] == 0
    assert by_key[("exact_four", "digest_split")]["sybil_gain_vs_one_key"] == 0
    assert by_key[("exact_four", "hotkey")]["sybil_gain_vs_one_key"] >= 0
    assert all(0 <= row["p_best_paid_final"] <= 1 for row in rows)
    assert all(row["attacker_target_fraction"] <= 1 for row in rows)
    output = json.dumps(rows)
    assert all(
        token not in output
        for token in ("attacker-0", "case_id", "recipe_digest", '"seed"')
    )


def test_prospective_assumptions_and_public_source_fail_closed(tmp_path):
    cfg = fixture_config()
    validate(cfg)
    bad = copy.deepcopy(cfg)
    bad["near_threshold_tight"] = bad["near_threshold_wide"]
    with pytest.raises(ValueError, match="ordered"):
        validate(bad)
    bad = copy.deepcopy(cfg)
    bad["base_simulation"]["public_noise_sha256"] = "0" * 64
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="pinned public-practice"):
        main([str(manifest), str(tmp_path / "curves.csv")])
    assert not (tmp_path / "curves.csv").exists()


def test_synthetic_credit_and_best_model_are_distinct():
    cfg = fixture_config()["base_simulation"]
    cfg.update(
        weak_coordinate=0.04,
        near_step=0.01,
        near_threshold_tight=0.012,
        near_threshold_wide=0.055,
        comparison_windows=1,
    )
    result = episode(
        cfg,
        scenario="copy_best_attacker_first",
        policy="digest_first",
        margin=0.0,
        decay=0.5,
        score_sd=0.0,
        replicate=0,
    )
    assert result["best_paid_final"] == 1
    assert result["attacker_target_fraction"] > 0


def test_wide_near_grouping_can_block_best_and_decay_changes_only_target():
    cfg = fixture_config()["base_simulation"]
    cfg.update(
        weak_coordinate=0.04,
        near_step=0.01,
        near_threshold_tight=0.012,
        near_threshold_wide=0.055,
        comparison_windows=1,
    )
    args = {
        "cfg": cfg,
        "scenario": "near_four",
        "policy": "near_first_wide",
        "margin": 0.05,
        "score_sd": 0.0,
        "replicate": 0,
    }
    fast_decay = episode(**args, decay=0.5)
    no_decay = episode(**args, decay=1.0)
    assert fast_decay["best_paid_final"] == no_decay["best_paid_final"] == 0
    assert fast_decay["false_merges"] > 0
    assert no_decay["paid_budget_fraction"] > fast_decay["paid_budget_fraction"]

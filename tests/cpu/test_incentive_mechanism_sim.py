"""Synthetic, offline checks for the prospective incentive analysis only."""

import ast
import copy
import hashlib
import json
import random
from pathlib import Path

import pytest

from scripts.dev.incentive_mechanism_sim import (
    Q12,
    STRATEGIES,
    Candidate,
    _candidates,
    _episode,
    _promotion_age_origin,
    _score_pair,
    _screen_and_final,
    _target_units,
    canary_predictions,
    main,
    public_noise_proxy,
    simulate,
    validate,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/development/incentive-mechanism-sim/assumptions.v1.json"


def fixture_config():
    cfg = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cfg.update(
        cases_per_comparison=30,
        important_cases=10,
        exposure_limit=2,
        windows_per_decay_period=3,
        horizon_windows=8,
        timing_arrival_window=2,
        margins=[cfg["registered_equivalence_margin_rel"]],
        decays=[0.5],
        comparison_windows=[1],
        replicates=3,
    )
    return cfg


def test_public_panel_digest_and_scale_are_pinned():
    cfg = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source = MANIFEST.parent / cfg["public_noise_source"]
    noise = public_noise_proxy(source, cfg["public_noise_sha256"])
    assert noise["recipes"] == 9
    assert noise["scores"] == 27
    assert 0.001 < noise["median_within_recipe_sd"] < 0.004
    with pytest.raises(ValueError, match="digest mismatch"):
        public_noise_proxy(source, "0" * 64)


def test_simulation_replay_and_aggregate_disclosure():
    cfg = fixture_config()
    noise = {"median_within_recipe_sd": 0.002}
    rows = simulate(cfg, noise)
    assert rows == simulate(cfg, noise)
    assert len(rows) == 2 * len(STRATEGIES)
    assert {row["comparison"] for row in rows} == {
        "paired_same_case",
        "unpaired_counterfactual",
    }
    assert all(0 <= row["p_best_paid_final"] <= 1 for row in rows)
    assert all(0 <= row["burn_fraction_of_challenge_budget"] <= 1 for row in rows)
    keys = json.dumps(rows)
    assert all(
        forbidden not in keys
        for forbidden in ("hotkey", "recipe_digest", "case_id", "seed", "winner_id")
    )


def test_registered_rule_metadata_and_owner_assumptions_are_explicit():
    cfg = fixture_config()
    validate(cfg)
    # AST reads just the public development constant, without importing
    # optional NumPy or any runtime/hidden reference path.
    tree = ast.parse((ROOT / "carbon/battery/exam.py").read_text(encoding="utf-8"))
    rule = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "DEVELOPMENT_RULE"
            for target in node.targets
        )
    )
    rule_fields = {
        key.value: value
        for key, value in zip(rule.keys, rule.values, strict=True)
        if isinstance(key, ast.Constant)
    }
    assert cfg["registered_equivalence_margin_rel"] == ast.literal_eval(
        rule_fields["equivalence_margin_rel"]
    )
    assert cfg["registered_comparison"] == ast.literal_eval(rule_fields["comparison"])
    assert cfg["exposure_limit"] != 5
    # The toy fixture deliberately varies E; the tracked manifest pins current E.
    tracked = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert tracked["exposure_limit"] == 5
    with pytest.raises(ValueError, match="registered rule"):
        altered = copy.deepcopy(cfg)
        altered["margins"] = [0.2]
        validate(altered)


def test_copy_cannot_promote_without_a_measured_gain_in_noiseless_case():
    rng = random.Random(1)
    same = _candidates("copy", 1, 0.074, 0.05, fixture_config())[-1]
    assert (
        _screen_and_final(
            rng,
            0.074,
            [same],
            margin=0.05,
            score_sd=0.0,
            paired=True,
            common_fraction=0.75,
            bank_shift=0.0,
            n=30,
            n_important=10,
            alpha=0.05,
            evidence_windows=1,
        )
        is None
    )


def test_sybil_has_separate_hotkeys_but_one_actor_and_no_coldkey_clock_reset():
    cfg = fixture_config()
    candidates = _candidates("sybil", 1, 0.074, 0.05, cfg)
    attackers = [c for c in candidates if c.actor == "attacker"]
    assert len(attackers) == cfg["sybil_hotkeys"]
    assert len({c.hotkey for c in attackers}) == cfg["sybil_hotkeys"]
    assert _promotion_age_origin(2, 7, attackers[0], attackers[1]) == 2
    assert (
        _promotion_age_origin(
            2, 7, Candidate("initial", "initial", 0.074), attackers[0]
        )
        == 7
    )
    out = _episode(
        random.Random(4),
        cfg,
        strategy="sybil",
        margin=0.05,
        decay=0.5,
        evidence_windows=1,
        paired=True,
        score_sd=0.002,
    )
    assert out["promotions"] >= 0
    assert out["paid_fraction_of_challenge_budget"] <= 1


def test_halving_target_matches_current_q12_winner_arithmetic():
    from carbon.rewards.core import DAY_MS
    from carbon.rewards.winner_decay import winner_fraction

    share = Q12 // 8
    for age in (0, 1, 2, 7):
        assert (
            _target_units(share, age, 0.5)
            == share * winner_fraction(0, age * DAY_MS) // Q12
        )


def test_timing_and_comparison_windows_are_bounded():
    cfg = fixture_config()
    assert _candidates("timing", 1, 0.074, 0.05, cfg) == []
    assert _candidates("timing", 2, 0.074, 0.05, cfg)[0].actor == "attacker"
    cfg["comparison_windows"] = [cfg["horizon_windows"]]
    with pytest.raises(ValueError, match="horizon too short"):
        validate(cfg)


def test_multiwindow_final_delays_payment_and_canary_keeps_observation_empty():
    cfg = fixture_config()
    cfg["horizon_windows"] = 10
    first = _episode(
        random.Random(1),
        cfg,
        strategy="honest",
        margin=cfg["margins"][0],
        decay=0.5,
        evidence_windows=1,
        paired=True,
        score_sd=0.0,
    )
    third = _episode(
        random.Random(1),
        cfg,
        strategy="honest",
        margin=cfg["margins"][0],
        decay=0.5,
        evidence_windows=3,
        paired=True,
        score_sd=0.0,
    )
    assert first["time_to_best_uncensored"] == 1
    assert third["time_to_best_uncensored"] == 3
    noise = {"median_within_recipe_sd": 0.002, "source_sha256": "toy"}
    bundle = canary_predictions(cfg, noise, simulate(cfg, noise))
    assert bundle["status"] == "SYNTHETIC_PREDICTION_NOT_LIVE_EVIDENCE"
    assert all(row["observed"] is None for row in bundle["rows"])


def test_public_noise_source_rejects_unpinned_toy_mutation(tmp_path):
    source = tmp_path / "practice.json"
    source.write_text(
        json.dumps(
            {
                "a": {"recipe_digest": "r1", "summary": {"score": 1.0}},
                "b": {"recipe_digest": "r1", "summary": {"score": 1.2}},
                "c": {"recipe_digest": "r2", "summary": {"score": 2.0}},
                "d": {"recipe_digest": "r2", "summary": {"score": 2.3}},
            }
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert public_noise_proxy(source, digest)["repeated_recipes"] == 2
    source.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        public_noise_proxy(source, digest)


def test_cli_refuses_a_manifest_pointing_away_from_public_panel(tmp_path):
    cfg = fixture_config()
    manifest = tmp_path / "assumptions.json"
    manifest.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ValueError, match="only the committed public practice"):
        main([str(manifest), str(tmp_path / "curves.csv")])
    assert not (tmp_path / "curves.csv").exists()


def test_paired_common_case_component_cancels_from_score_difference():
    paired = _score_pair(
        random.Random(11),
        0.07,
        0.065,
        score_sd=0.01,
        paired=True,
        common_fraction=1.0,
        bank_shift=0,
    )
    unpaired = _score_pair(
        random.Random(11),
        0.07,
        0.065,
        score_sd=0.01,
        paired=False,
        common_fraction=1.0,
        bank_shift=0,
    )
    assert paired[1] - paired[0] == pytest.approx(-0.005)
    assert unpaired[1] - unpaired[0] != pytest.approx(-0.005)

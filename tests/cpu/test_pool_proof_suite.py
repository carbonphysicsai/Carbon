"""The pool grader's proof suite, on a toy plugin (spec POOL_GRADER_AND_PROOF_SUITE_SPEC_20261024, section 3).

All values are SYNTHETIC test numbers on a two-variable toy problem; none is a production threshold.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from carbon.challenge_validator import exam_rotation
from carbon.scoring import pool_grader
from carbon.scoring import pool_proof_suite as suite
from carbon.scoring.pool_grader import (
    HonestyPolicy,
    Limit,
    OptimizerPolicy,
    build_target,
)

U = 0.01
POLICIES = suite.Policies(
    optimizer=OptimizerPolicy(budget=90, sigma0=0.3, population=None),
    honesty=HonestyPolicy(scale=5.0, reduction="max"),
    agen_scales={"f": 0.1, "g": 0.1},
    a_rule={"kind": "min"},
    c_rule={"kind": "min"},
)
PARAMS = suite.SuiteParams(
    oracle_tolerance=1e-9,
    k_grid=(0.0, 1.0, 2.0, 4.0, 8.0),
    monotone_tolerance=0.02,
    optimism_k=30.0,
    wrong_radius=0.15,
    wrong_k=12.0,
    leak_rounds=12,
    leak_step=1.0,
    ladder_decimals=2,
    koth_margin=0.02,
    near_optimum_radius=0.15,
    near_limit_u=10.0,
    bins=5,
    separation_target=0.85,
    seed=7,
    resamples=50,
)


def outputs_of(x, y):
    return {"f": x + y, "g": x * x + y * y}


def toy_target(name, pool_seed, seed):
    rng = random.Random(pool_seed)
    points = [(rng.random(), rng.random()) for _ in range(60)]
    points += [
        (0.63 + rng.uniform(-0.12, 0.12), 0.63 + rng.uniform(-0.12, 0.12))
        for _ in range(40)
    ]
    return build_target(
        target_id=name,
        conditions={"case": name},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", 0.8),),
        u={"f": U, "g": U},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=[list(p) for p in points],
        truths=[outputs_of(*p) for p in points],
        agen=range(92, 100),
        start=(0.5, 0.5),
        seed=seed,
    )


def toy_sets():
    return tuple(
        tuple(
            toy_target(f"s{s}t{t}", pool_seed=10 * s + t, seed=100 * s + t)
            for t in range(3)
        )
        for s in range(2)
    )


def truth_table(sets):
    table = {}
    for specs in sets:
        for spec in specs:
            for design, truth in zip(spec.designs, spec.truths):
                table[(spec.conditions["case"], design)] = truth
    return table


def noisy_good(sets, noise_k=2.0):
    table = truth_table(sets)

    def predict(conditions, designs):
        out = []
        for design in designs:
            truth = table[(conditions["case"], tuple(design))]
            sign = suite._sign("test", conditions["case"], list(design))
            out.append(
                {
                    "f": truth["f"] + sign * noise_k * U,
                    "g": truth["g"] + sign * noise_k * U,
                }
            )
        return out

    return predict


def default_model(conditions, designs):
    return [{"f": 0.9, "g": 0.5} for _ in designs]


def plugin_with(sets, good, fresh_sets=None):
    legs_table = {
        "oracle": (1.0, 1.0),
        "good": (0.9, 0.95),
        "default": (0.5, 0.6),
        "in_distribution": (0.6, 0.7),
    }

    def legs(descriptor, specs):
        kind = descriptor["kind"]
        if kind == "noisy":
            return {
                "A": 1.0 / (1.0 + 0.05 * descriptor["k"]),
                "C": 1.0 / (1.0 + 0.05 * descriptor["k"]),
            }
        if kind == "wrong_near_optimum":
            return {"A": 0.95, "C": 0.95}
        if kind == "perturbed":
            a, c = legs_table[descriptor["base"]["kind"]]
            return {"A": a, "C": c}
        a, c = legs_table[kind]
        return {"A": a, "C": c}

    def fresh_set(draw):
        if fresh_sets is not None:
            return fresh_sets
        return tuple(
            toy_target(f"fresh{draw}t{t}", pool_seed=900 + t, seed=900 + t)
            for t in range(3)
        )

    return suite.ProofPlugin(
        sets=sets,
        fresh_set=fresh_set,
        train_box=lambda spec: ((0.0, 0.5), (0.0, 0.5)),
        train_model=lambda conditions, designs: [outputs_of(*d) for d in designs],
        default_model=default_model,
        good_model=good,
        legs=legs,
    )


def build_plugin(noise_k=2.0):
    sets = toy_sets()
    fresh = tuple(
        toy_target(f"fresh7t{t}", pool_seed=900 + t, seed=900 + t) for t in range(3)
    )
    all_sets = sets + (fresh,)
    return plugin_with(sets, noisy_good(all_sets, noise_k), fresh_sets=fresh)


def test_an_oracle_is_perfect_on_every_leg_and_reaches_every_reference():
    result = suite.check_oracle_is_perfect(build_plugin(), POLICIES, PARAMS)
    assert result["verdict"] == "PASS", result
    assert result["numbers"]["reached"] == result["numbers"]["targets"] == 6
    assert all(t == pytest.approx(1.0) for t in result["numbers"]["totals"])


def test_an_oracle_that_cannot_reach_the_reference_within_the_budget_fails_and_says_so():
    tiny = suite.Policies(
        optimizer=OptimizerPolicy(budget=2, sigma0=0.3, population=2),
        honesty=POLICIES.honesty,
        agen_scales=POLICIES.agen_scales,
        a_rule=POLICIES.a_rule,
        c_rule=POLICIES.c_rule,
    )
    result = suite.check_oracle_is_perfect(build_plugin(), tiny, PARAMS)
    assert result["verdict"] == "FAIL" and "too small" in result["numbers"]["note"]


def test_the_strictness_curve_falls_monotonically_with_injected_error_in_both_modes():
    result = suite.check_strictness_curve(build_plugin(), POLICIES, PARAMS)
    assert result["verdict"] == "PASS", result
    for mode in ("random", "feasible_bias"):
        totals = [t for _, t in result["numbers"]["curves"][mode]]
        assert totals[0] == pytest.approx(1.0) and totals[-1] < totals[0]


def test_the_gaming_controls_each_score_below_the_good_model():
    result = suite.check_gaming_controls_lose(build_plugin(), POLICIES, PARAMS)
    assert result["verdict"] == "PASS", result
    assert all(
        score < result["numbers"]["good"]
        for score in result["numbers"]["controls"].values()
    )


def test_coverage_reports_numbers_and_has_no_pass_rule():
    plugin = build_plugin()
    result = suite.check_coverage(plugin, PARAMS, {"s0t0": 17})
    assert result["verdict"] == "REPORT_ONLY"
    row = result["numbers"]["targets"][0]
    assert (
        row["pool"] <= 100
        and row["near_optimum"] > 0
        and row["agen_points"] >= 1
        and row["queries"] == 17
    )
    assert 0.0 < row["box_share"] <= 1.0 and 0.0 < row["agen_box_share"] <= 1.0
    assert len(result["numbers"]["targets"]) == 6


def test_the_leak_attack_passes_an_honest_good_model_and_fails_one_that_memorised_the_sealed_sets():
    honest = suite.check_leak_attack(build_plugin(), POLICIES, PARAMS)
    assert honest["verdict"] == "PASS", honest
    assert honest["numbers"]["gain"] <= honest["numbers"]["threshold"]
    sets = toy_sets()
    sealed_table = truth_table(sets)

    def memorised(conditions, designs):
        return [
            (
                dict(sealed_table[(conditions["case"], tuple(d))])
                if (conditions["case"], tuple(d)) in sealed_table
                else {"f": 5.0, "g": 5.0}
            )
            for d in designs
        ]

    fresh = tuple(
        toy_target(f"fresh7t{t}", pool_seed=900 + t, seed=900 + t) for t in range(3)
    )
    leaky = suite.check_leak_attack(
        plugin_with(sets, memorised, fresh_sets=fresh), POLICIES, PARAMS
    )
    assert leaky["verdict"] == "FAIL", leaky
    assert leaky["numbers"]["gain"] > leaky["numbers"]["threshold"]


def test_the_leak_threshold_is_the_weekly_overfit_rule():
    for margin, se_s, se_f in ((0.02, 0.01, 0.03), (0.0, 0.0, 0.0), (0.05, 0.02, 0.02)):
        assert suite.leak_threshold(margin, se_s, se_f) == pytest.approx(
            exam_rotation.threshold(margin, se_s, se_f)
        )


def test_separation_rule_takes_the_larger_of_a_tenth_and_five_margins():
    assert (
        suite.separation(0.80, 0.69, target=0.80, koth_margin=0.02)["verdict"] == "PASS"
    )
    assert (
        suite.separation(0.80, 0.71, target=0.80, koth_margin=0.02)["verdict"] == "FAIL"
    )  # gap 0.09 < 0.10
    assert (
        suite.separation(0.80, 0.69, target=0.80, koth_margin=0.03)["verdict"] == "FAIL"
    )  # needs 0.15
    assert (
        suite.separation(0.81, 0.50, target=0.80, koth_margin=0.02)["verdict"] == "FAIL"
    )  # good above target


def test_the_whole_suite_runs_deterministically_and_discloses_only_numbers():
    plugin = build_plugin()
    first = suite.run_suite(plugin, POLICIES, PARAMS)
    again = suite.run_suite(plugin, POLICIES, PARAMS)
    assert first == again
    assert set(first) >= {
        "1_oracle",
        "2_strictness",
        "3_gaming_controls",
        "4_coverage",
        "5_leak_attack",
        "6_separation",
        "all_pass",
    }
    text = json.dumps(first)
    assert "designs" not in text and "truths" not in text
    # No design vector of the pool appears in the report.
    spec = plugin.sets[0][0]
    assert not any(repr(round(x, 6)) in text for x in spec.designs[0])


def test_a_model_descriptor_must_be_known_and_conditions_must_identify_one_target():
    plugin = build_plugin()
    with pytest.raises(pool_grader.PoolRefused):
        suite.pool_predictor(plugin, {"kind": "mystery"}, [])
    twin = toy_target("same", 1, 1)
    with pytest.raises(pool_grader.PoolRefused):
        suite.pool_predictor(plugin, {"kind": "oracle"}, [twin, twin])


def test_the_suite_names_no_challenge():
    source = Path(suite.__file__).read_text(encoding="utf-8").lower()
    for name in ("motor", "cooling", "battery", "f02", "f08", "ribbed", "burst"):
        assert name not in source, name

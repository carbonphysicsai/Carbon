"""The top-k design rule of the pool grader (new exam versions only; week-1 item: top-k design regret).

Claims: with no rule, or k = 1, the grade is today's single pick bit for bit; with ``{"kind": "top_k", "k": k}`` a target is
graded on the model's k best distinct feasible-predicted designs: q is the verified quality of the BEST truth among them,
the honesty factor is the MEAN of exp(-e_i / s_h) over the k picks (a missing slot counts as infeasible: h_i = 0), and
d = q * h; a lucky single pick no longer carries a target, a confidently wrong pick among the k lowers h, a registered version
without a rule is unchanged, k has no default, and the proof suite's gaming controls still lose under k = 3.
Every number is a SYNTHETIC test value on the toy two-variable problem."""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

from carbon.scoring import pool_grader, pool_version
from carbon.scoring import pool_proof_suite as suite
from carbon.scoring.pool_grader import (
    OptimizerPolicy,
    PoolRefused,
    grade_target,
)
from tests.cpu.test_pool_grader import HONESTY, OPTIMIZER, U, oracle, toy_target
from tests.cpu.test_pool_proof_suite import PARAMS, POLICIES, build_plugin

K3 = {"kind": "top_k", "k": 3}


def with_rule(rule, base=OPTIMIZER):
    return dataclasses.replace(base, pick_rule=rule)


def noisy(spec, scale):
    """The oracle plus a deterministic error of ``scale`` U on both outputs, signed per design."""
    truth = oracle([spec])

    def predict(conditions, designs):
        out = []
        for d, row in zip(designs, truth(conditions, designs), strict=True):
            sign = 1.0 if math.floor(sum(d) * 1000) % 2 else -1.0
            out.append({k: v + sign * scale * U for k, v in row.items()})
        return out

    return predict


# --- k = 1 and no rule are today's grade --------------------------------------------------------------------------


@pytest.mark.parametrize("scale", [0.0, 1.0, 3.0, 8.0])
def test_no_rule_and_k_equal_one_reproduce_todays_grade_bit_for_bit(scale):
    for i in range(3):
        spec = toy_target(f"t{i}", seed=i)
        predict = noisy(spec, scale)
        today = grade_target(spec, predict, OPTIMIZER, HONESTY)
        explicit_none = grade_target(spec, predict, with_rule(None), HONESTY)
        one = grade_target(spec, predict, with_rule({"kind": "top_k", "k": 1}), HONESTY)
        assert today == explicit_none == one
        assert today.picks == ()


# --- the formula, with the picks chosen by hand --------------------------------------------------------------------


def _quality(spec, index):
    s = spec.sign * spec.truths[index][spec.objective]
    return min(1.0, max(0.0, (s - spec.s_low) / (spec.s_ref - spec.s_low)))


def _scene():
    spec = toy_target("scene", seed=4)
    feasible = [i for i in spec.queryable if spec.feasible[i]]
    ranked = sorted(feasible, key=lambda i: -_quality(spec, i))
    infeasible = [i for i in spec.queryable if not spec.feasible[i]]
    assert spec.reference == ranked[0] and _quality(spec, ranked[0]) == 1.0
    return spec, ranked, infeasible


def _grade(spec, claims, k, honesty=HONESTY):
    """`_top_k_grade` with the picks chosen by hand: ``claims`` is the model's ranking, best first, as ``(design index,
    error in U)``; its predicted f is the truth plus that error and its g is exact."""
    predictions = {
        index: {
            "f": spec.truths[index]["f"] + error_u * U,
            "g": spec.truths[index]["g"],
        }
        for index, error_u in claims
    }
    order = {index: n for n, (index, _) in enumerate(claims)}
    key = lambda i: (0, order[i])  # the model's own ranking
    return pool_grader._top_k_grade(
        spec,
        predictions,
        [index for index, _ in claims],
        key,
        with_rule({"kind": "top_k", "k": k}),
        honesty,
    )


def test_q_is_the_best_truth_among_the_k_and_h_is_the_mean_factor():
    spec, ranked, _ = _scene()
    # (5 U and 10 U errors with s_h = 5: factors exp(-1) and exp(-2); the first is exact)
    grade = _grade(spec, [(ranked[0], 0.0), (ranked[1], 5.0), (ranked[2], 10.0)], 3)
    expected_h = (1.0 + math.exp(-1.0) + math.exp(-2.0)) / 3
    assert grade.reason == "graded" and grade.q == 1.0
    assert grade.h == pytest.approx(expected_h) and grade.d == pytest.approx(expected_h)
    assert [p[0] for p in grade.picks] == ranked[:3]


def test_a_lucky_single_pick_no_longer_carries_the_target():
    spec, ranked, _ = _scene()
    best, other_a, other_b = ranked[0], ranked[3], ranked[4]
    lucky = [
        (best, 0.0),
        (other_a, 20.0),
        (other_b, 20.0),
    ]  # the top pick is the reference; the follow-ups are overclaims
    honest = [(best, 0.0), (other_a, 0.0), (other_b, 0.0)]
    assert (
        _grade(spec, lucky, 1).d == _grade(spec, honest, 1).d == pytest.approx(1.0)
    )  # k = 1 cannot tell them apart
    assert _grade(spec, lucky, 3).d < _grade(spec, honest, 3).d == pytest.approx(1.0)


def test_a_confidently_wrong_pick_among_the_k_lowers_h():
    spec, ranked, _ = _scene()
    exact = _grade(spec, [(ranked[0], 0.0), (ranked[1], 0.0), (ranked[2], 0.0)], 3)
    wrong = _grade(spec, [(ranked[0], 0.0), (ranked[1], 0.0), (ranked[2], 30.0)], 3)
    assert wrong.q == exact.q and wrong.h < exact.h and wrong.d < exact.d


def test_k_three_rewards_a_model_whose_second_and_third_picks_are_good():
    spec, ranked, _ = _scene()
    weak_top = ranked[-1]
    good_follow_ups = [(weak_top, 0.0), (ranked[0], 0.0), (ranked[1], 0.0)]
    weak_follow_ups = [(weak_top, 0.0), (ranked[-2], 0.0), (ranked[-3], 0.0)]
    one_good, one_weak = _grade(spec, good_follow_ups, 1), _grade(
        spec, weak_follow_ups, 1
    )
    assert one_good.d == one_weak.d  # the single (weak) top pick is graded the same
    three_good, three_weak = _grade(spec, good_follow_ups, 3), _grade(
        spec, weak_follow_ups, 3
    )
    assert three_good.q == 1.0 and three_weak.q < 1.0 and three_good.d > three_weak.d


def test_a_missing_slot_counts_as_infeasible_and_a_truly_infeasible_pick_has_no_quality():
    spec, ranked, infeasible = _scene()
    short = _grade(spec, [(ranked[0], 0.0)], 3)
    assert short.q == 1.0 and short.h == pytest.approx(
        1 / 3
    )  # one exact pick, two empty slots
    assert short.picks[1:] == ((None, 0.0, 0.0), (None, 0.0, 0.0))
    mixed = _grade(spec, [(ranked[0], 0.0), (infeasible[0], 0.0), (ranked[1], 0.0)], 3)
    assert mixed.q == 1.0 and mixed.reason == "graded" and mixed.picks[1][1] == 0.0
    assert mixed.h == pytest.approx(
        1.0
    )  # the infeasible pick's claim was exact: only its quality is 0
    dead = _grade(spec, [(i, 0.0) for i in infeasible[:3]], 3)
    assert dead.reason == "pick_infeasible" and dead.d == 0.0 and not dead.feasible


def test_end_to_end_the_oracle_is_perfect_under_k_three_with_the_same_queries():
    spec = toy_target("e2e", seed=9)
    predict = oracle([spec])
    one = grade_target(spec, predict, OPTIMIZER, HONESTY)
    three = grade_target(spec, predict, with_rule(K3), HONESTY)
    assert (
        three.reason == "graded"
        and three.d == 1.0
        and three.h == 1.0
        and three.q == 1.0
    )
    assert three.queries == one.queries  # the rule changes the grade, not the search
    assert len({p[0] for p in three.picks}) == 3 and three.pick == one.pick
    # a model that overclaims on its follow-ups is graded lower than the oracle
    shaky = grade_target(spec, noisy(spec, 6.0), with_rule(K3), HONESTY)
    assert shaky.d < 1.0


# --- the registration ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rule",
    [
        {"kind": "top_k"},
        {"kind": "top_k", "k": 0},
        {"kind": "top_k", "k": 2.0},
        {"kind": "top_k", "k": True},
        {"kind": "best_of", "k": 3},
        {"kind": "top_k", "k": 3, "extra": 1},
        "top_k",
    ],
)
def test_a_malformed_rule_is_refused(rule):
    with pytest.raises(PoolRefused, match="pick_rule"):
        grade_target(toy_target(), oracle([toy_target()]), with_rule(rule), HONESTY)


def test_a_policy_without_a_rule_is_the_default_object_and_k_is_never_defaulted():
    assert OptimizerPolicy(budget=5, sigma0=0.3, population=None).pick_rule is None
    assert (
        pool_grader.pick_count(OPTIMIZER) == 1
        and pool_grader.pick_count(with_rule(K3)) == 3
    )
    assert pool_version._pick_rule(None) is None
    assert pool_version._pick_rule(K3) == K3
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version._pick_rule({"kind": "top_k", "k": pool_version.HUMAN_INPUT})
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version._pick_rule({"kind": "top_k"})


def test_every_registered_version_keeps_the_single_pick():
    document = json.loads(pool_version.CONSTANTS.read_bytes())
    for name, entry in document["versions"].items():
        challenge, version = name.rsplit(" ", 1)
        try:
            policies = pool_version.registered_policies(challenge, version)
        except pool_version.PoolConstantsNotRegistered:
            continue  # a version whose owner values are still HUMAN_INPUT grades nothing
        assert policies.optimizer.pick_rule is None, name
        assert "pick_rule" not in entry["optimizer"], name


# --- the proof suite under k = 3 ----------------------------------------------------------------------------------------


def _k3_policies():
    return dataclasses.replace(POLICIES, optimizer=with_rule(K3, POLICIES.optimizer))


def test_the_oracle_is_still_perfect_and_the_gaming_controls_still_lose_under_k_three():
    plugin = build_plugin()
    oracle_result = suite.check_oracle_is_perfect(plugin, _k3_policies(), PARAMS)
    assert oracle_result["verdict"] == "PASS", oracle_result
    gaming = suite.check_gaming_controls_lose(plugin, _k3_policies(), PARAMS)
    assert gaming["verdict"] == "PASS", gaming
    assert all(
        score < gaming["numbers"]["good"]
        for score in gaming["numbers"]["controls"].values()
    )
    curve = suite.check_strictness_curve(plugin, _k3_policies(), PARAMS)
    assert curve["verdict"] == "PASS", curve


def test_the_grid_spec_carries_the_rule_without_changing_the_old_files():
    from carbon.scoring import pool_proof_grid as grid

    fields = {f.name: f for f in dataclasses.fields(grid.GridSpec)}
    assert (
        fields["pick_rule"].default is None
    )  # an old grid file has no such key and means the single pick

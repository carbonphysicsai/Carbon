"""Near-limit picks scored by TRUE margin with U (owner option (a2), 4 Nov; Validator 22:01 K2 ruling), new versions only.

Claims: with no rule every target and grade is today's (within-U points dropped); with ``{"kind": "credit_ramp",
"shape": "linear"}`` the within-U points stay, each point's credit is 0 when truly infeasible, margin / U inside U and 1
beyond; the reference is the best credit x gain over the zero; the pick is the best PREDICTED value; so an exact model
scores q = 1 even when the reference is a near-limit point (the Validator's test), a pick inside U is never a clean
pass, and a pick inside U on the wrong side is infeasible (0, as today). The rule is part of the pool's identity and
must match the version's; the top-k rule and HUMAN_INPUT refuse. SYNTHETIC toy values only (U = 0.01 on g = x^2 + y^2
<= 0.8, f = x + y maximised); none is a production U, ramp or threshold.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
from test_pool_grader import HONESTY, OPTIMIZER, U, oracle, outputs_of

from carbon.scoring import pool_version
from carbon.scoring.pool_grader import (
    Limit,
    PoolRefused,
    build_target,
    dump_pool,
    grade_target,
    load_pool,
)

RULE = {"kind": "credit_ramp", "shape": "linear"}
CLEAN = [(0.1, 0.1), (0.2, 0.2), (0.3, 0.3), (0.4, 0.4), (0.5, 0.5), (0.55, 0.55)]


def on_g(g):
    """The diagonal point with g = x^2 + y^2 = ``g``."""
    x = math.sqrt(g / 2.0)
    return (x, x)


def target(points, near_limit=RULE, target_id="n"):
    return build_target(
        target_id=target_id,
        conditions={"case": target_id},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", 0.8),),
        u={"f": U, "g": U},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=[list(p) for p in points],
        truths=[outputs_of(*p) for p in points],
        agen=(),
        start=(0.5, 0.5),
        seed=3,
        near_limit=near_limit,
    )


def exhaustive(spec, rule=RULE):
    return replace(OPTIMIZER, budget=len(spec.designs), near_limit=rule)


NEAR_09 = on_g(0.8 - 0.9 * U)  # margin 0.9 U: credit 0.9
NEAR_05 = on_g(0.8 - 0.5 * U)  # margin 0.5 U: credit 0.5
WRONG_SIDE = on_g(0.8 + 0.5 * U)  # truly infeasible, inside U: credit 0
FAR_OUT = (0.7, 0.7)  # g = 0.98: clearly infeasible


def test_without_a_rule_the_target_is_todays():
    points = CLEAN + [NEAR_09, WRONG_SIDE, FAR_OUT]
    today = target(points, near_limit=None)
    assert today.excluded == 2 and len(today.designs) == len(points) - 2
    assert today.near_limit is None and today.credit == () and today.v_ref is None
    assert "near_limit" not in dump_pool(today)
    with_rule = target(points)
    assert with_rule.excluded == 0 and len(with_rule.designs) == len(points)
    assert with_rule.digest != today.digest  # the rule is part of the identity


def test_credit_is_zero_infeasible_margin_over_u_inside_and_one_beyond():
    spec = target(CLEAN + [NEAR_09, NEAR_05, WRONG_SIDE, FAR_OUT])
    by_design = dict(zip(spec.designs, spec.credit, strict=True))
    assert all(by_design[tuple(map(float, p))] == 1.0 for p in CLEAN)
    assert by_design[NEAR_09] == pytest.approx(0.9, abs=1e-9)
    assert by_design[NEAR_05] == pytest.approx(0.5, abs=1e-9)
    assert by_design[WRONG_SIDE] == 0.0 and by_design[FAR_OUT] == 0.0
    # s_low is the median over CLEAN feasible points only
    assert spec.s_low == pytest.approx(0.7, abs=1e-12)


def test_an_exact_model_scores_one_when_the_reference_is_a_near_limit_point():
    """The Validator's test (22:01): the pick uses the same credit, so a perfect model reaches q = 1."""
    spec = target(CLEAN + [NEAR_09, WRONG_SIDE, FAR_OUT])
    assert (
        spec.designs[spec.reference] == NEAR_09
    )  # 0.9 x (1.258 - 0.7) beats 1.0 x (1.1 - 0.7)
    grade = grade_target(spec, oracle([spec]), exhaustive(spec), HONESTY)
    assert (
        grade.q == 1.0 and grade.reached_reference is True and grade.reason == "graded"
    )
    # today's grader on the same points cannot see that optimum: it was dropped
    today = target(CLEAN + [NEAR_09, WRONG_SIDE, FAR_OUT], near_limit=None)
    assert NEAR_09 not in today.designs


def test_a_pick_inside_u_is_never_a_clean_pass():
    spec = target(CLEAN + [NEAR_05, FAR_OUT])
    reference = spec.designs[spec.reference]
    assert reference == (0.55, 0.55)  # 0.5 x (1.26 - 0.7) < 1.0 x (1.1 - 0.7)
    exact = oracle([spec])

    def overconfident(conditions, designs):
        """Right everywhere except that it calls the near-limit point clean (g predicted well inside the limit)."""
        rows = exact(conditions, designs)
        return [
            {**r, "g": 0.5} if tuple(d) == NEAR_05 else r
            for d, r in zip(designs, rows, strict=True)
        ]

    grade = grade_target(spec, overconfident, exhaustive(spec), HONESTY)
    assert spec.designs[grade.pick] == NEAR_05
    expected = 0.5 * (sum(NEAR_05) - spec.s_low) / spec.v_ref
    assert grade.q == pytest.approx(expected, abs=1e-9) and grade.q < 1.0
    assert grade.reached_reference is False
    assert grade_target(spec, exact, exhaustive(spec), HONESTY).q == 1.0


def test_a_pick_inside_u_on_the_wrong_side_is_infeasible():
    spec = target(CLEAN + [WRONG_SIDE, FAR_OUT])
    exact = oracle([spec])

    def thinks_it_fits(conditions, designs):
        rows = exact(conditions, designs)
        return [
            {**r, "g": 0.7} if tuple(d) == WRONG_SIDE else r
            for d, r in zip(designs, rows, strict=True)
        ]

    grade = grade_target(spec, thinks_it_fits, exhaustive(spec), HONESTY)
    assert spec.designs[grade.pick] == WRONG_SIDE
    assert grade.reason == "pick_infeasible" and grade.d == 0.0


def test_the_rule_must_match_the_version_and_refuses_what_it_does_not_cover():
    spec = target(CLEAN + [NEAR_09, FAR_OUT])
    today = target(CLEAN + [NEAR_09, FAR_OUT], near_limit=None)
    with pytest.raises(PoolRefused, match="near_limit_differs"):
        grade_target(spec, oracle([spec]), OPTIMIZER, HONESTY)
    with pytest.raises(PoolRefused, match="near_limit_differs"):
        grade_target(today, oracle([today]), exhaustive(today), HONESTY)
    for bad in (
        {"kind": "credit_ramp"},
        {"kind": "credit_ramp", "shape": "cubic"},
        {"kind": "clean_only", "shape": "linear"},
        "HUMAN_INPUT",
    ):
        with pytest.raises(PoolRefused, match="near_limit_must_be"):
            grade_target(spec, oracle([spec]), exhaustive(spec, bad), HONESTY)
        with pytest.raises(PoolRefused, match="near_limit_must_be"):
            target(CLEAN, near_limit=bad)
    top_k = replace(exhaustive(spec), pick_rule={"kind": "top_k", "k": 2})
    with pytest.raises(PoolRefused, match="near_limit_needs_the_single_pick"):
        grade_target(spec, oracle([spec]), top_k, HONESTY)


def test_too_few_clean_points_or_no_credited_gain_is_a_degenerate_reference():
    with pytest.raises(PoolRefused, match="two_clean_feasible"):
        target([(0.1, 0.1), NEAR_09, NEAR_05, FAR_OUT])


def test_the_pool_document_carries_the_rule_and_round_trips():
    spec = target(CLEAN + [NEAR_09, WRONG_SIDE, FAR_OUT])
    document = dump_pool(spec)
    assert document["near_limit"] == RULE
    again = load_pool(document)
    assert again.digest == spec.digest and again.near_limit == RULE
    assert again.credit == spec.credit and again.v_ref == spec.v_ref


def test_the_registration_reads_the_rule_with_no_default():
    assert pool_version._near_limit(pool_version._ABSENT) is None
    for bad in (None, "HUMAN_INPUT", {"kind": "credit_ramp", "shape": "HUMAN_INPUT"}):
        with pytest.raises(pool_version.PoolConstantsNotRegistered):
            pool_version._near_limit(bad)
    assert pool_version._near_limit(dict(RULE)) == RULE


def test_neighbour_task_variants_carry_the_rule_and_grade_with_it():
    import random

    from carbon.scoring.pool_grader import attach_variants, variant_slots

    rng = random.Random(4)
    points = (
        CLEAN + [NEAR_09, FAR_OUT] + [(rng.random(), rng.random()) for _ in range(60)]
    )
    spec = target(points)
    rule = {
        "kind": "limit_shift",
        "limits": ["g"],
        "shifts": [-0.05, 0.05],
        "min_valid": 1,
        "aggregate": "mean",
    }
    starts = [
        {"start": [0.5, 0.5], "seed": 9 + n} for n in range(len(variant_slots(rule)))
    ]
    attached = attach_variants(spec, rule, starts)
    assert attached.variants and all(v.near_limit == RULE for v in attached.variants)
    policy = replace(exhaustive(spec), variant_rule=rule)
    grade = grade_target(attached, oracle([spec]), policy, HONESTY)
    assert grade.base_d == pytest.approx(
        1.0 * grade.h
    )  # the exact model reaches each question's reference
    assert all(d == pytest.approx(1.0, abs=1e-12) for _v, d, _r in grade.variants)

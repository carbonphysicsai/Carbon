"""Neighbour-task robustness of D on the pool path (OWNER-DESIGN-DECISION-FIDELITY-01: V_var; Validator note 4 Nov 21:20).

Claims (the note's four tests first):
1. ``variant_rule`` None is today's D bit for bit (values pinned from main d8581915's unchanged grader).
2. A variant whose reference degenerates is REFUSED and counted (a reference failure), never scored 0.
3. The per-point prediction cache gives the same D as grading every question uncached, with fewer model calls.
4. An exact model gets the same D on every variant.
Plus: D(target) = mean over the base and its valid variants, or the base alone below ``min_valid`` (reported); a variant
uses only the base's kept pool points (no new exam row); every owner value refuses as HUMAN_INPUT; custody starts/seeds
per variant are required and checked.

Every number is a SYNTHETIC toy value (f = x + y under g = x^2 + y^2 <= 0.8); none is a production shift, minimum,
budget or scale.
"""

from __future__ import annotations

import json
import random
from dataclasses import replace

import pytest
from test_pool_grader import HONESTY, OPTIMIZER, U, oracle, outputs_of, toy_target

from carbon.scoring import pool_exam, pool_version
from carbon.scoring.pool_grader import (
    Limit,
    PoolRefused,
    attach_variants,
    build_target,
    grade_set,
    grade_target,
    variant_slots,
)


def _rule(shifts=(-0.05, 0.05), min_valid=1, limits=("g",)):
    return {
        "kind": "limit_shift",
        "limits": list(limits),
        "shifts": list(shifts),
        "min_valid": min_valid,
        "aggregate": "mean",
    }


def _starts(rule, seed=100):
    return [
        {"start": [0.5, 0.5], "seed": seed + n} for n in range(len(variant_slots(rule)))
    ]


def _with(rule):
    return replace(OPTIMIZER, variant_rule=rule)


def _noisy(predict):
    """A deterministic per-POINT error (the same answer whichever question asks): needed for the cache test."""

    def noisy(conditions, designs):
        out = predict(conditions, designs)
        return [
            {k: v + 0.02 * ((round(d[0] * 997) % 3) - 1) for k, v in row.items()}
            for d, row in zip(designs, out, strict=True)
        ]

    return noisy


# ---------------------------------------------------------------- 1. None is today, bit for bit


def test_no_variant_rule_is_todays_d_bit_for_bit():
    """Pinned from main d8581915's grader (before this change) on the same three toy targets."""
    specs = [toy_target(f"t{n}", seed=11 + n, pool_seed=3 + n) for n in range(3)]
    exact = oracle(specs)

    def noisy(conditions, designs):  # main's pinned noisy model (index-in-batch error)
        return [
            {k: v + 0.02 * (i % 3 - 1) for k, v in r.items()}
            for i, r in enumerate(exact(conditions, designs))
        ]

    golden = {
        "exact": (1.0, [(66, 1.0, 50), (81, 1.0, 50), (80, 1.0, 50)]),
        "noisy": (
            0.7713633433449489,
            [(64, 0.6437699839992078, 50), (81, 0.6703200460356391, 50), (80, 1.0, 50)],
        ),
    }
    for name, predict in (("exact", exact), ("noisy", noisy)):
        grade = grade_set(specs, predict, OPTIMIZER, HONESTY)
        assert grade.d == golden[name][0]
        assert [(t.pick, t.d, t.queries) for t in grade.targets] == golden[name][1]
        # and attaching variants changes nothing while the rule is None
        rule = _rule()
        attached = [attach_variants(s, rule, _starts(rule)) for s in specs]
        assert grade_set(attached, predict, OPTIMIZER, HONESTY) == grade


# ---------------------------------------------------------------- 2. a degenerate variant is a reference failure


def test_a_degenerate_variant_is_refused_and_counted_never_scored_zero():
    spec = toy_target("t0")
    rule = _rule(
        shifts=(-0.99, 0.05), min_valid=1
    )  # g <= 0.008: too few feasible points for a reference
    attached = attach_variants(spec, rule, _starts(rule))
    assert [v.target_id for v in attached.variants] == ["t0~g+0.05"]
    ((name, shift, code),) = attached.variant_refusals
    assert (name, shift) == ("g", -0.99) and code.startswith("degenerate_reference")
    predict = _noisy(oracle([spec]))
    grade = grade_target(attached, predict, _with(rule), HONESTY)
    base = grade_target(spec, predict, OPTIMIZER, HONESTY)
    ((_vid, variant_d, _reason),) = grade.variants
    assert grade.base_d == base.d
    assert grade.d == pytest.approx(
        (base.d + variant_d) / 2
    )  # the refused one is not a 0 in the mean
    assert grade.variant_refusals == 1 and grade.variant_fallback is False


# ---------------------------------------------------------------- 3. the cache changes calls, never D


def test_the_prediction_cache_gives_the_same_d_as_uncached_with_fewer_model_calls():
    spec = toy_target("t0")
    rule = _rule(shifts=(-0.05, 0.05, 0.1))
    attached = attach_variants(spec, rule, _starts(rule))
    calls = {"cached": 0, "uncached": 0}
    model = _noisy(oracle([spec]))

    def counting(kind):
        def predict(conditions, designs):
            calls[kind] += len(designs)
            return model(conditions, designs)

        return predict

    cached = grade_target(attached, counting("cached"), _with(rule), HONESTY)
    # uncached: every question graded on its own, a fresh model call per query
    base = grade_target(spec, counting("uncached"), OPTIMIZER, HONESTY)
    variants = [
        grade_target(v, counting("uncached"), OPTIMIZER, HONESTY)
        for v in attached.variants
    ]
    expected = (base.d + sum(v.d for v in variants)) / (1 + len(variants))
    assert cached.d == pytest.approx(expected, abs=1e-15)
    assert [d for _v, d, _r in cached.variants] == [v.d for v in variants]
    assert calls["cached"] < calls["uncached"]


# ---------------------------------------------------------------- 4. an exact model is equally right on every variant


def test_an_exact_model_gets_the_same_d_on_every_variant():
    spec = toy_target("t0", agen_count=0)
    exhaustive = replace(
        OPTIMIZER, budget=len(spec.designs)
    )  # every point asked: the exact model finds each optimum
    rule = _rule(shifts=(-0.05, 0.05))
    attached = attach_variants(spec, rule, _starts(rule))
    grade = grade_target(
        attached, oracle([spec]), replace(exhaustive, variant_rule=rule), HONESTY
    )
    assert grade.base_d == 1.0
    assert [d for _v, d, _r in grade.variants] == [1.0, 1.0]
    assert grade.d == 1.0


# ---------------------------------------------------------------- the rule's other behaviour


def test_below_min_valid_the_target_falls_back_to_its_base_d_and_says_so():
    spec = toy_target("t0")
    rule = _rule(shifts=(-0.99, 0.05), min_valid=2)  # only one of two is valid
    attached = attach_variants(spec, rule, _starts(rule))
    predict = _noisy(oracle([spec]))
    grade = grade_target(attached, predict, _with(rule), HONESTY)
    assert grade.variant_fallback is True and grade.d == grade.base_d
    assert grade.d == grade_target(spec, predict, OPTIMIZER, HONESTY).d


def test_a_variant_asks_only_about_the_bases_kept_pool_points():
    """The exam's one table of model answers covers the base's kept rows; a variant never adds a row."""
    spec = toy_target("t0")
    rule = _rule(shifts=(-0.05, 0.05, 0.2))
    attached = attach_variants(spec, rule, _starts(rule))
    kept = set(spec.designs)
    for variant in attached.variants:
        assert set(variant.designs) <= kept
        assert variant.truths == tuple(
            spec.truths[spec.designs.index(d)] for d in variant.designs
        )


def test_variant_refusal_codes_for_a_missing_limit_a_zero_bound_and_no_choice_left():
    rng = random.Random(7)
    points = [
        (rng.uniform(0, 0.8), rng.uniform(0, 0.8)) for _ in range(80)
    ]  # g <= 1.28 everywhere
    spec = build_target(
        target_id="z",
        conditions={"case": "z"},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", 0.8), Limit("f", ">=", 0.0)),
        u={"f": U, "g": U},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=[list(p) for p in points],
        truths=[outputs_of(*p) for p in points],
        agen=(),
        start=(0.5, 0.5),
        seed=1,
    )
    rule = _rule(shifts=(0.9,), limits=("g", "f", "h"), min_valid=0)
    attached = attach_variants(spec, rule, _starts(rule))
    assert attached.variants == ()
    assert [code for _n, _s, code in attached.variant_refusals] == [
        "variant_pool_has_no_infeasible_point",  # g <= 1.52 holds for every point
        "variant_shift_moves_nothing",  # f >= 0 x 1.9
        "variant_limit_not_on_target",
    ]


def test_a_rule_without_attached_variants_refuses_and_malformed_rules_refuse():
    spec = toy_target("t0")
    with pytest.raises(PoolRefused, match="variants_not_attached"):
        grade_target(spec, oracle([spec]), _with(_rule()), HONESTY)
    for bad in (
        {**_rule(), "kind": "objective_swap"},
        {**_rule(), "shifts": [0.0]},
        {**_rule(), "shifts": [0.05, 0.05]},
        {**_rule(), "shifts": [1.0]},
        {**_rule(), "limits": []},
        {**_rule(), "min_valid": 3},  # more than the 2 slots
        {**_rule(), "aggregate": "min"},
        {k: v for k, v in _rule().items() if k != "min_valid"},
        "HUMAN_INPUT",
    ):
        with pytest.raises(PoolRefused, match="variant_rule"):
            grade_target(spec, oracle([spec]), _with(bad), HONESTY)
    with pytest.raises(PoolRefused, match="one_start_and_seed_per_slot"):
        attach_variants(spec, _rule(), _starts(_rule())[:1])


def test_only_the_set_d_is_public_with_variants():
    spec = toy_target("t0")
    rule = _rule()
    attached = attach_variants(spec, rule, _starts(rule))
    public = grade_set(
        [attached], _noisy(oracle([spec])), _with(rule), HONESTY
    ).public()
    assert set(public) == {"d", "reasons"}
    assert "~" not in json.dumps(public)  # no variant id leaves custody


# ---------------------------------------------------------------- the registered constants and the sealed material


def test_the_registered_rule_is_absent_for_todays_versions_and_never_defaulted():
    assert pool_version._variant_rule(pool_version._ABSENT) is None
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version._variant_rule(None)
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version._variant_rule("HUMAN_INPUT")
    for field in ("limits", "min_valid"):
        with pytest.raises(pool_version.PoolConstantsNotRegistered):
            pool_version._variant_rule({**_rule(), field: "HUMAN_INPUT"})
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version._variant_rule({**_rule(), "limits": ["HUMAN_INPUT"]})
    assert pool_version._variant_rule(_rule()) == _rule()


def test_the_sealed_material_must_carry_one_start_per_slot_of_every_target():
    specs = ((toy_target("t0"), toy_target("t1", seed=12, pool_seed=4)),)
    rule = _rule()
    assert pool_version.attach_material_variants(specs, None, None) is specs
    with pytest.raises(pool_exam.ExamRefused, match="without_a_variant_rule"):
        pool_version.attach_material_variants(specs, None, {"t0": []})
    with pytest.raises(pool_exam.ExamRefused, match="missing"):
        pool_version.attach_material_variants(specs, rule, None)
    with pytest.raises(pool_exam.ExamRefused, match="every_target_exactly"):
        pool_version.attach_material_variants(specs, rule, {"t0": _starts(rule)})
    attached = pool_version.attach_material_variants(
        specs, rule, {"t0": _starts(rule), "t1": _starts(rule, seed=200)}
    )
    assert all(len(s.variants) == 2 for group in attached for s in group)
    assert attached[0][0].digest == specs[0][0].digest  # the base identity is unchanged

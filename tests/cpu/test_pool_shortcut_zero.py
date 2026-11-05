"""The engineer's-shortcut D zero (OWNER-DESIGN-VALUE-ENGINEER-BASELINE-01; Validator 21:22 / 21:30, 4 Nov).

Claims: with no zero a target is byte-identical to origin/main d8581915 (its digest is pinned); an ANCHORED zero sets the target's
zero to the shortcut's objective (q measured from it), and one at or above the reference refuses at build (the sampler redraws);
``no_verified_feasible`` / ``not_screened`` keep the median zero, recorded in the identity; a zero computed on another pool, a
malformed zero and a policy/target mismatch refuse; the zero survives dump/load; the registered constants parse ``d_zero`` (absent =
None, HUMAN_INPUT refuses). The flip (the king audit's "beats the shortcut" row): a model that only reaches the shortcut's level
scores a high D under the median zero and 0 under the shortcut zero, while a model that beats the shortcut keeps its D. Every value
is synthetic (a toy two-variable problem).
"""

from __future__ import annotations

import random

import pytest

from carbon.scoring import pool_grader, pool_version
from carbon.scoring.pool_grader import (
    HonestyPolicy,
    Limit,
    OptimizerPolicy,
    PoolRefused,
    build_target,
    dump_pool,
    grade_target,
    load_pool,
)

HONESTY = HonestyPolicy(scale=5.0, reduction="max")
BUDGET_B = 8  # synthetic
RECORD = "a" * 64
#: The toy target's digest at origin/main d8581915 (computed from that commit's pool_grader): no zero = unchanged.
MAIN_DIGEST = "sha256:9c91841c952ed79df76c7256e96de3b0b3e7473731bc8a0939b0885635ade31a"


def _points():
    rng = random.Random(3)
    points = [(rng.random(), rng.random()) for _ in range(60)]
    points += [
        (0.63 + rng.uniform(-0.12, 0.12), 0.63 + rng.uniform(-0.12, 0.12))
        for _ in range(40)
    ]
    return points


def _toy(zero=None):
    points = _points()
    return build_target(
        target_id="t0",
        conditions={"case": "t0"},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", 0.8),),
        u={"f": 0.01, "g": 0.01},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=[list(p) for p in points],
        truths=[{"f": x + y, "g": x * x + y * y} for x, y in points],
        agen=range(92, 100),
        start=(0.5, 0.5),
        seed=11,
        zero=zero,
    )


def _zero(status, s_zero=None, *, pool_digest=None, budget=BUDGET_B):
    doc = {
        "kind": "engineer_shortcut",
        "budget": budget,
        "status": status,
        "record_sha256": RECORD,
        "pool_digest": MAIN_DIGEST if pool_digest is None else pool_digest,
    }
    if s_zero is not None:
        doc["s_zero"] = s_zero
    return doc


def _policy(d_zero=None, budget=50):
    return OptimizerPolicy(budget=budget, sigma0=0.3, population=None, d_zero=d_zero)


SHORTCUT = {"kind": "engineer_shortcut", "budget": BUDGET_B}


def test_no_zero_is_byte_identical_to_main():
    spec = _toy()
    assert spec.digest == MAIN_DIGEST and spec.zero is None
    assert "zero" not in dump_pool(spec)
    assert OptimizerPolicy(budget=5, sigma0=0.3, population=None).d_zero is None


def test_an_anchored_zero_is_the_shortcuts_objective_and_enters_the_identity():
    base = _toy()
    s_zero = base.s_low + 0.5 * (base.s_ref - base.s_low)
    spec = _toy(_zero("anchored", s_zero))
    assert spec.s_low == s_zero and spec.s_ref == base.s_ref
    assert spec.digest != base.digest and spec.zero["s_zero"] == s_zero
    assert load_pool(dump_pool(spec)) == spec


@pytest.mark.parametrize("status", ["no_verified_feasible", "not_screened"])
def test_unanchored_statuses_keep_the_median_zero_recorded(status):
    base = _toy()
    spec = _toy(_zero(status))
    assert spec.s_low == base.s_low and spec.zero["status"] == status
    assert spec.digest != base.digest  # recorded in the identity
    assert load_pool(dump_pool(spec)) == spec


def test_a_shortcut_that_reaches_the_reference_refuses_so_the_sampler_redraws():
    base = _toy()
    for s_zero in (base.s_ref, base.s_ref + 1.0):
        with pytest.raises(
            PoolRefused, match="degenerate_shortcut_reaches_the_reference"
        ):
            _toy(_zero("anchored", s_zero))


def test_a_zero_from_another_pool_or_malformed_refuses():
    base = _toy()
    with pytest.raises(PoolRefused, match="zero_is_not_this_pools"):
        _toy(_zero("anchored", base.s_low, pool_digest="sha256:" + "0" * 64))
    bad = [
        {**_zero("anchored", base.s_low), "kind": "median"},
        {**_zero("anchored", base.s_low), "budget": 0},
        {**_zero("anchored", base.s_low), "status": "guessed"},
        {**_zero("anchored", base.s_low), "record_sha256": "short"},
        {**_zero("anchored", base.s_low), "extra": 1},
        _zero("anchored"),  # anchored without s_zero
        _zero("no_verified_feasible", base.s_low),  # s_zero only when anchored
        {**_zero("anchored", base.s_low), "s_zero": float("nan")},
        "anchored",
    ]
    for zero in bad:
        with pytest.raises(PoolRefused, match="zero_malformed|zero_must_be_a_dict"):
            _toy(zero)


def test_the_policy_and_the_targets_zero_must_agree():
    plain, zeroed = _toy(), _toy(_zero("no_verified_feasible"))
    predict = _oracle(plain)
    with pytest.raises(PoolRefused, match="target_zero_without_a_registered_d_zero"):
        grade_target(zeroed, predict, _policy(), HONESTY)
    with pytest.raises(
        PoolRefused, match="target_zero_differs_from_the_registered_d_zero"
    ):
        grade_target(plain, predict, _policy(SHORTCUT), HONESTY)
    with pytest.raises(
        PoolRefused, match="target_zero_differs_from_the_registered_d_zero"
    ):
        grade_target(
            zeroed,
            predict,
            _policy({"kind": "engineer_shortcut", "budget": 4}),
            HONESTY,
        )
    for bad in (
        {"kind": "median", "budget": 4},
        {"kind": "engineer_shortcut", "budget": 0},
        {"kind": "engineer_shortcut"},
    ):
        with pytest.raises(
            PoolRefused, match="d_zero_must_be_none_or_engineer_shortcut"
        ):
            grade_target(zeroed, predict, _policy(bad), HONESTY)
    assert grade_target(zeroed, predict, _policy(SHORTCUT), HONESTY).reason == "graded"


def _oracle(spec, cap=None):
    """Predicts the truth; with ``cap`` it predicts every design whose objective is above the cap as infeasible, so its pick
    can reach the cap but never beat it (a model that only matches the engineer's shortcut).
    """
    table = {tuple(d): t for d, t in zip(spec.designs, spec.truths)}

    def predict(conditions, designs):
        out = []
        for d in designs:
            truth = dict(table[tuple(d)])
            if cap is not None and truth["f"] > cap:
                truth["g"] = 10.0
            out.append(truth)
        return out

    return predict


def test_the_flip_a_model_that_only_ties_the_shortcut_scores_zero_under_the_shortcut_zero():
    base = _toy()
    cap = base.s_low + 0.9 * (
        base.s_ref - base.s_low
    )  # the shortcut reaches 90 % of the way from the median
    feasible = sorted(
        s
        for n, t in enumerate(base.truths)
        if base.feasible[n] and n in base.queryable and (s := t["f"]) <= cap
    )
    s_shortcut = feasible[
        -1
    ]  # the shortcut's achieved objective: the best feasible design at or below the cap
    zeroed = _toy(_zero("anchored", s_shortcut))
    ties = _oracle(base, cap=cap)
    median_d = grade_target(base, ties, _policy(), HONESTY)
    shortcut_d = grade_target(zeroed, ties, _policy(SHORTCUT), HONESTY)
    # under the median zero the tie looks like strong design value; under the shortcut zero it is worth nothing
    assert median_d.reason == "graded" and median_d.d > 0.5 and median_d.q > 0.5
    # D = 0 because q = 0 at a feasible, honest pick (not an infeasible pick or a dishonest prediction)
    assert shortcut_d.reason == "graded" and shortcut_d.d == 0.0
    assert shortcut_d.feasible and shortcut_d.q == 0.0 and shortcut_d.h == 1.0
    # a model that beats the shortcut keeps its design value under the shortcut zero
    beats = grade_target(zeroed, _oracle(base), _policy(SHORTCUT), HONESTY)
    assert beats.reason == "graded" and beats.d > 0.0 and beats.reached_reference


def test_the_registered_constants_parse_d_zero():
    absent = pool_version._ABSENT
    assert pool_version._d_zero(absent) is None
    assert pool_version._d_zero({"kind": "engineer_shortcut", "budget": 8}) == SHORTCUT
    for bad in (
        None,
        {"kind": "engineer_shortcut"},
        {"kind": "engineer_shortcut", "budget": 8, "x": 1},
    ):
        with pytest.raises(pool_version.PoolConstantsNotRegistered):
            pool_version._d_zero(bad)
    with pytest.raises(  # HUMAN_INPUT is never a budget
        pool_version.PoolConstantsNotRegistered, match="pool_constants_not_registered"
    ):
        pool_version._d_zero({"kind": "engineer_shortcut", "budget": "HUMAN_INPUT"})


def test_every_zero_status_is_named_in_the_module():
    assert pool_grader.ZERO_STATUSES == (
        "anchored",
        "no_verified_feasible",
        "not_screened",
    )
    assert pool_grader.D_ZERO_KIND == "engineer_shortcut"


# ---------------------------------------------------------------- the custody flow and the registered paths


def _source(zero=None):
    points = _points()
    doc = {
        "design_names": ["x", "y"],
        "target_id": "t0",
        "conditions": {"target_id": "t0", "fixed": {}},
        "outputs": ["f", "g"],
        "objective": "f",
        "sense": "max",
        "limits": [["g", "<=", 0.8]],
        "u": {"f": 0.01, "g": 0.01},
        "box": [[0.0, 1.0], [0.0, 1.0]],
        "designs": [list(p) for p in points],
        "truths": [{"f": x + y, "g": x * x + y * y} for x, y in points],
        "agen": list(range(92, 100)),
        "start": [0.5, 0.5],
        "seed": 11,
    }
    if zero is not None:
        doc["zero"] = zero
    return doc


def test_the_custody_flow_through_spec_from_source():
    """The shortcut run records the digest of the zero-less pool-source target; that digest is the zero's pool_digest."""
    from types import SimpleNamespace

    from carbon.scoring import pool_plugin

    binding = SimpleNamespace(design_names=("x", "y"))
    plain = pool_plugin.spec_from_source(_source(), binding)
    zero = {**_zero("anchored", plain.s_low + 0.01), "pool_digest": plain.digest}
    spec = pool_plugin.spec_from_source(_source(zero), binding)
    assert (
        spec.zero["s_zero"] == plain.s_low + 0.01 and spec.s_low == plain.s_low + 0.01
    )
    with pytest.raises(PoolRefused, match="zero_is_not_this_pools"):
        pool_plugin.spec_from_source(
            _source({**zero, "pool_digest": MAIN_DIGEST}), binding
        )


def _constants(tmp_path, d_zero):
    import json

    optimizer = {"budget": 40, "sigma0": 0.3, "population": 8}
    if d_zero is not pool_version._ABSENT:
        optimizer["d_zero"] = d_zero
    entry = {
        "optimizer": optimizer,
        "honesty": {"scale": 1.0, "reduction": "max"},
        "agen_scales": {"x": 1.0},
        "a_rule": {"kind": "test_fixture"},
        "c_rule": {"kind": "min"},
        "a_multiplier": 3.0,
    }
    path = tmp_path / "pool_constants.json"
    path.write_text(
        json.dumps(
            {"schema": pool_version.SCHEMA, "versions": {"fixture-x 9.9": entry}}
        )
    )
    return path


def test_registered_policies_read_d_zero_end_to_end(tmp_path):
    read = pool_version.registered_policies
    path = _constants(tmp_path, pool_version._ABSENT)
    assert read("fixture-x", "9.9", path=path).optimizer.d_zero is None
    path = _constants(tmp_path, SHORTCUT)
    assert read("fixture-x", "9.9", path=path).optimizer.d_zero == SHORTCUT
    for bad in (
        {"kind": "engineer_shortcut", "budget": True},
        {"kind": "engineer_shortcut", "budget": "8"},
        {"kind": "median", "budget": 8},
        None,
    ):
        with pytest.raises(pool_version.PoolConstantsNotRegistered):
            read("fixture-x", "9.9", path=_constants(tmp_path, bad))
    for unpicked in (
        "HUMAN_INPUT",
        {"kind": "engineer_shortcut", "budget": "HUMAN_INPUT"},
    ):
        with pytest.raises(
            pool_version.PoolConstantsNotRegistered,
            match="pool_constants_not_registered",
        ):
            read("fixture-x", "9.9", path=_constants(tmp_path, unpicked))


def test_the_set_path_grades_a_zeroed_set_and_refuses_a_mixed_one():
    base = _toy()
    zeroed = _toy(_zero("anchored", base.s_low + 0.5 * (base.s_ref - base.s_low)))
    result = pool_grader.grade_set([zeroed], _oracle(base), _policy(SHORTCUT), HONESTY)
    assert (
        result.d == 1.0
    )  # the oracle reaches the reference: full design value under either zero
    other = build_target(
        target_id="t1",
        conditions={"case": "t1"},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", 0.8),),
        u={"f": 0.01, "g": 0.01},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=[list(p) for p in _points()],
        truths=[{"f": x + y, "g": x * x + y * y} for x, y in _points()],
        agen=range(92, 100),
        start=(0.5, 0.5),
        seed=11,
    )
    with pytest.raises(
        PoolRefused, match="target_zero_differs_from_the_registered_d_zero"
    ):
        pool_grader.grade_set(
            [zeroed, other], _oracle(base), _policy(SHORTCUT), HONESTY
        )


def test_a_tampered_zero_in_a_dump_refuses_at_load():
    base = _toy()
    spec = _toy(_zero("anchored", base.s_low + 0.1))
    doc = dump_pool(spec)
    doc["zero"]["s_zero"] = base.s_low + 0.2  # the digest kept
    with pytest.raises(PoolRefused, match="pool_digest_does_not_match_its_content"):
        load_pool(doc)
    assert (
        spec.zero["s_zero"] == base.s_low + 0.1
    )  # the dump is a copy: the spec is untouched


def test_the_shortcut_zero_and_a_variant_rule_do_not_combine_until_ruled():
    """A variant re-asks the question with a shifted limit; the shortcut's anchor was run on the base question, so the two
    new-version rules refuse together (fail closed) until the Validator rules how a variant gets its zero.
    """
    rule = {
        "kind": "limit_shift",
        "limits": ["g"],
        "shifts": [-0.05, 0.05],
        "min_valid": 1,
        "aggregate": "mean",
    }
    zeroed = _toy(_zero("no_verified_feasible"))
    policy = OptimizerPolicy(
        budget=50, sigma0=0.3, population=None, variant_rule=rule, d_zero=SHORTCUT
    )
    with pytest.raises(PoolRefused, match="d_zero_with_a_variant_rule_needs_a_ruling"):
        grade_target(zeroed, _oracle(zeroed), policy, HONESTY)

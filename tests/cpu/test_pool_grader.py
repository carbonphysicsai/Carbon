"""The Challenge-neutral pool grader (OWNER-INVERSE-DESIGN-PROOF-01; spec POOL_GRADER_AND_PROOF_SUITE_SPEC_20261024).

Every number here is a SYNTHETIC test value on a toy two-variable problem; none is a production budget,
scale or threshold (those are OWNER picks and have no default in the module).
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import pytest

from carbon.scoring import pool_cmaes, pool_grader
from carbon.scoring.pool_grader import (
    HonestyPolicy,
    Limit,
    OptimizerPolicy,
    PoolRefused,
    build_target,
    grade_set,
    grade_target,
)

U = 0.01
OPTIMIZER = OptimizerPolicy(budget=50, sigma0=0.3, population=None)
HONESTY = HonestyPolicy(scale=5.0, reduction="max")


def outputs_of(x, y):
    return {"f": x + y, "g": x * x + y * y}


def toy_target(target_id="t0", seed=11, pool_seed=3, extra=(), agen_count=8):
    """f = x + y (maximise) subject to g = x^2 + y^2 <= 0.8; the optimum is near (0.632, 0.632)."""
    rng = random.Random(pool_seed)
    points = [(rng.random(), rng.random()) for _ in range(60)]
    points += [
        (0.63 + rng.uniform(-0.12, 0.12), 0.63 + rng.uniform(-0.12, 0.12))
        for _ in range(40)
    ]
    points += list(extra)
    designs = [list(p) for p in points]
    truths = [outputs_of(*p) for p in points]
    return build_target(
        target_id=target_id,
        conditions={"case": target_id},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", 0.8),),
        u={"f": U, "g": U},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=designs,
        truths=truths,
        agen=range(len(points) - agen_count, len(points)) if agen_count else (),
        start=(0.5, 0.5),
        seed=seed,
    )


def oracle(spec_by_case):
    table = {}
    for spec in spec_by_case:
        for design, truth in zip(spec.designs, spec.truths):
            table[(spec.conditions["case"], design)] = truth

    def predict(conditions, designs):
        return [dict(table[(conditions["case"], tuple(d))]) for d in designs]

    return predict


def test_the_oracle_reaches_the_reference_optimum_on_every_target():
    specs = [toy_target(f"t{i}", seed=i) for i in range(3)]
    result = grade_set(specs, oracle(specs), OPTIMIZER, HONESTY)
    assert [t.reason for t in result.targets] == ["graded"] * 3
    assert all(
        t.reached_reference and t.d == 1.0 and t.h == 1.0 for t in result.targets
    )
    assert result.d == 1.0
    assert all(t.queries <= OPTIMIZER.budget for t in result.targets)


def test_grading_is_deterministic_for_the_same_model_and_seed_and_the_seed_matters():
    spec = toy_target()
    predict = oracle([spec])
    first = grade_target(spec, predict, OPTIMIZER, HONESTY)
    again = grade_target(spec, predict, OPTIMIZER, HONESTY)
    assert first == again
    other = toy_target(seed=12)
    asked_a, asked_b = [], []

    def record(into):
        base = oracle([spec])

        def predict_recorded(conditions, designs):
            into.extend(map(tuple, designs))
            return base(conditions, designs)

        return predict_recorded

    grade_target(spec, record(asked_a), OPTIMIZER, HONESTY)
    grade_target(other, record(asked_b), OPTIMIZER, HONESTY)
    assert asked_a != asked_b, "a different private seed explores differently"


def test_the_model_is_only_asked_about_queryable_pool_points_within_the_budget_in_batches():
    spec = toy_target()
    agen = {spec.designs[i] for i in spec.agen}
    batches = []
    base = oracle([spec])

    def predict(conditions, designs):
        batches.append([tuple(d) for d in designs])
        return base(conditions, designs)

    grade_target(
        spec, predict, OptimizerPolicy(budget=30, sigma0=0.3, population=6), HONESTY
    )
    asked = [d for batch in batches for d in batch]
    assert (
        len(asked) == len(set(asked)) <= 30
    ), "each point is queried once, within the budget"
    assert not agen & set(asked), "the A_gen slice is never queried"
    assert max(len(b) for b in batches) <= 6 and len(batches) > 1


def test_points_within_u_of_a_limit_are_excluded_when_the_pool_is_built():
    # g = 0.8 exactly and 0.805 are within U of the limit; 0.7 is clear.
    near = [(math.sqrt(0.4), math.sqrt(0.4)), (math.sqrt(0.4025), math.sqrt(0.4025))]
    base = toy_target(agen_count=0)
    spec = toy_target(extra=near, agen_count=0)
    assert spec.excluded == base.excluded + 2
    assert all(abs(0.8 - t["g"]) > U for t in spec.truths)


def test_an_optimistic_model_that_steers_to_an_infeasible_design_loses_to_the_good_model():
    spec = toy_target()
    base = oracle([spec])

    def optimistic(conditions, designs):
        return [{"f": t["f"], "g": t["g"] - 0.25} for t in base(conditions, designs)]

    good = grade_target(spec, base, OPTIMIZER, HONESTY)
    bad = grade_target(spec, optimistic, OPTIMIZER, HONESTY)
    assert bad.d < good.d
    assert bad.reason in ("pick_infeasible", "graded")


def test_honesty_scales_with_the_models_error_at_its_final_pick():
    spec = toy_target()
    base = oracle([spec])

    def shifted(k):
        def predict(conditions, designs):
            return [
                {"f": t["f"] + k * U, "g": t["g"]} for t in base(conditions, designs)
            ]

        return predict

    exact = grade_target(spec, shifted(0), OPTIMIZER, HONESTY)
    off = grade_target(spec, shifted(5), OPTIMIZER, HONESTY)
    assert exact.h == 1.0 and exact.d == 1.0
    assert off.pick == exact.pick and off.q == 1.0
    assert off.e == pytest.approx(5.0) and off.h == pytest.approx(math.exp(-1.0))
    assert off.d == pytest.approx(math.exp(-1.0))
    rms = grade_target(
        spec, shifted(5), OPTIMIZER, HonestyPolicy(scale=5.0, reduction="rms")
    )
    assert rms.e == pytest.approx(5.0 / math.sqrt(2.0))


def test_a_target_with_no_predicted_feasible_pick_or_a_malformed_prediction_scores_zero_with_a_code():
    spec = toy_target()
    base = oracle([spec])

    def nothing_feasible(conditions, designs):
        return [{"f": t["f"], "g": 5.0} for t in base(conditions, designs)]

    assert (
        grade_target(spec, nothing_feasible, OPTIMIZER, HONESTY).reason
        == "no_predicted_feasible_pick"
    )
    for broken in (
        lambda c, d: [{"f": 1.0}] * len(d),
        lambda c, d: [{"f": math.nan, "g": 0.0}] * len(d),
        lambda c, d: [],
    ):
        grade = grade_target(spec, broken, OPTIMIZER, HONESTY)
        assert grade.reason == "prediction_invalid" and grade.d == 0.0

    def crashed(conditions, designs):
        raise RuntimeError("sandbox died")

    with pytest.raises(RuntimeError):
        grade_target(
            spec, crashed, OPTIMIZER, HONESTY
        )  # infrastructure, never a candidate score


def test_a_pool_that_cannot_give_a_reference_is_refused_not_scored():
    only_one = {
        "target_id": "t",
        "conditions": {},
        "outputs": ("f", "g"),
        "objective": "f",
        "sense": "max",
        "limits": (Limit("g", "<=", 0.8),),
        "u": {"f": U, "g": U},
        "box": ((0.0, 1.0), (0.0, 1.0)),
        "designs": [[0.1, 0.1], [0.9, 0.9], [0.95, 0.95]],
        "truths": [outputs_of(0.1, 0.1), outputs_of(0.9, 0.9), outputs_of(0.95, 0.95)],
        "agen": (),
        "start": (0.5, 0.5),
        "seed": 1,
    }
    with pytest.raises(PoolRefused, match="degenerate_reference"):
        build_target(**only_one)
    bad = dict(only_one, start=(2.0, 0.5))
    with pytest.raises(PoolRefused, match="start_must_be_in_the_unit_box"):
        build_target(**bad)
    with pytest.raises(PoolRefused, match="u_must_cover"):
        build_target(**dict(only_one, u={"f": U}))


def test_no_owner_constant_has_a_default():
    with pytest.raises(TypeError):
        OptimizerPolicy(budget=10)  # sigma0 and population are required too
    with pytest.raises(TypeError):
        HonestyPolicy(scale=1.0)
    spec = toy_target()
    for policy in (
        OptimizerPolicy(budget=0, sigma0=0.3, population=None),
        OptimizerPolicy(budget=5, sigma0=-1.0, population=None),
        OptimizerPolicy(budget=5, sigma0=0.3, population=1),
    ):
        with pytest.raises(PoolRefused):
            grade_target(spec, oracle([spec]), policy, HONESTY)
    with pytest.raises(PoolRefused):
        grade_target(
            spec, oracle([spec]), OPTIMIZER, HonestyPolicy(scale=0.0, reduction="max")
        )
    with pytest.raises(PoolRefused):
        grade_target(
            spec, oracle([spec]), OPTIMIZER, HonestyPolicy(scale=1.0, reduction="mean")
        )


def test_only_the_set_d_and_closed_codes_are_public():
    specs = [toy_target("a", seed=1), toy_target("b", seed=2)]
    base = oracle(specs)

    def nothing_feasible(conditions, designs):
        return [{"f": t["f"], "g": 5.0} for t in base(conditions, designs)]

    result = grade_set(specs, nothing_feasible, OPTIMIZER, HONESTY)
    public = result.public()
    assert set(public) == {"d", "reasons"} and public["d"] == 0.0
    assert public["reasons"] == ["no_predicted_feasible_pick"]
    text = repr(public)
    assert "pick" not in text.replace("no_predicted_feasible_pick", "")
    assert set(pool_grader.REASONS) >= set(public["reasons"])


def test_a_gen_accuracy_uses_only_the_reserved_slice_and_combines_by_the_owners_rule():
    spec = toy_target()
    base = oracle([spec])
    scales = {"f": 0.1, "g": 0.1}
    assert pool_grader.agen_accuracy([spec], base, scales) == 1.0

    def off(conditions, designs):
        return [{"f": t["f"] + 0.1, "g": t["g"]} for t in base(conditions, designs)]

    value = pool_grader.agen_accuracy([spec], off, scales)
    assert value == pytest.approx(0.5 * (1.0 + 0.5))  # f atoms 1/(1+1) = 0.5, g atoms 1
    assert pool_grader.agen_accuracy([toy_target(agen_count=0)], base, scales) is None
    with pytest.raises(PoolRefused):
        pool_grader.agen_accuracy([spec], base, {"f": 0.1})
    assert pool_grader.combine_a(0.9, 0.6, {"kind": "min"}) == 0.6
    assert pool_grader.combine_a(0.9, 0.6, {"kind": "mean"}) == pytest.approx(0.75)
    assert pool_grader.combine_a(
        0.9, 0.6, {"kind": "weighted", "weight": 0.25}
    ) == pytest.approx(0.825)
    assert pool_grader.combine_a(0.9, None, {"kind": "min"}) == 0.9
    with pytest.raises(PoolRefused):
        pool_grader.combine_a(0.9, 0.6, {})


def test_the_total_keeps_half_and_half_with_c_as_a_floor_by_the_owners_choice():
    assert pool_grader.total(0.8, 0.6, 0.9, {"kind": "min"}) == pytest.approx(0.7)
    assert pool_grader.total(0.8, 0.6, 0.4, {"kind": "min"}) == pytest.approx(
        0.6
    )  # D = min(D, C) = 0.4
    assert pool_grader.total(0.8, 0.6, 0.4, {"kind": "gate", "floor": 0.5}) == 0.0
    assert pool_grader.total(
        0.8, 0.6, 0.9, {"kind": "gate", "floor": 0.5}
    ) == pytest.approx(0.7)
    with pytest.raises(PoolRefused):
        pool_grader.total(0.8, 0.6, 0.9, {})


def test_the_module_names_no_challenge():
    """OWNER-MODULAR-CHALLENGES-01: a Challenge plugs in data and a predictor; there is no Challenge list here."""
    for module in (pool_grader, pool_cmaes):
        source = Path(module.__file__).read_text(encoding="utf-8").lower()
        for name in ("motor", "cooling", "battery", "f02", "f08", "ribbed", "burst"):
            assert name not in source, (module.__name__, name)


def test_the_eigensolver_and_cmaes_are_correct_and_deterministic():
    values, vectors = pool_cmaes._jacobi_eigh([[2.0, 1.0], [1.0, 2.0]])
    assert values == pytest.approx([1.0, 3.0])
    reconstructed = [
        [
            sum(vectors[r][i] * values[i] * vectors[c][i] for i in range(2))
            for c in range(2)
        ]
        for r in range(2)
    ]
    assert [x for row in reconstructed for x in row] == pytest.approx(
        [2.0, 1.0, 1.0, 2.0]
    )

    def run():
        es = pool_cmaes.CmaEs([0.8, 0.8], 0.3, seed=5)
        best = math.inf
        for _ in range(40):
            samples = es.ask()
            keys = [(x - 0.2) ** 2 + (y - 0.3) ** 2 for x, y in samples]
            best = min(best, min(keys))
            es.tell(keys)
        return best, es.mean

    first, again = run(), run()
    assert first == again
    assert first[0] < 1e-6 and first[1] == pytest.approx([0.2, 0.3], abs=1e-2)
    with pytest.raises(ValueError):
        pool_cmaes.CmaEs([0.5], 0.0, seed=1)


def public_toy(target_id="p0", seed=5):
    base = toy_target(target_id, seed=seed)
    document = pool_grader.dump_pool(base)
    document["public"] = True
    document.pop("digest")
    return build_public(document)


def build_public(document):
    return build_target(
        target_id=document["target_id"],
        conditions=document["conditions"],
        outputs=document["outputs"],
        objective=document["objective"],
        sense=document["sense"],
        limits=[Limit(*row) for row in document["limits"]],
        u=document["u"],
        box=document["box"],
        designs=document["designs"],
        truths=document["truths"],
        agen=document["agen"],
        start=document["start"],
        seed=document["seed"],
        public=True,
    )


def test_a_pool_round_trips_through_its_document_and_its_digest_is_its_identity():
    spec = toy_target("rt")
    document = pool_grader.dump_pool(spec)
    assert document["schema"] == "carbon.pool.v1" and document["digest"] == spec.digest
    import json

    again = pool_grader.load_pool(json.loads(json.dumps(document)))
    assert again == spec
    tampered = json.loads(json.dumps(document))
    tampered["truths"][0]["f"] += 1e-6
    with pytest.raises(PoolRefused, match="digest"):
        pool_grader.load_pool(tampered)
    relabelled = json.loads(json.dumps(document))
    relabelled["public"] = True  # a sealed pool cannot be relabelled public
    with pytest.raises(PoolRefused, match="digest"):
        pool_grader.load_pool(relabelled)
    with pytest.raises(PoolRefused, match="schema"):
        pool_grader.load_pool({"schema": "other"})


def test_the_practice_report_needs_a_public_pool_and_gives_legs_gates_and_every_targets_values():
    sealed = toy_target("s")
    with pytest.raises(PoolRefused, match="pool_not_public"):
        pool_grader.practice_report(
            [sealed],
            oracle([sealed]),
            OPTIMIZER,
            HONESTY,
            a=1.0,
            c=1.0,
            a_rule={"kind": "min"},
            agen_scales={"f": 0.1, "g": 0.1},
            c_rule={"kind": "min"},
        )
    public = public_toy()
    kwargs = {
        "a": 0.9,
        "c": 0.8,
        "a_rule": {"kind": "min"},
        "agen_scales": {"f": 0.1, "g": 0.1},
        "c_rule": {"kind": "min"},
        "gates": [{"code": "physics_contract", "passed": True}],
        "minimums": {"A": 0.5},
    }
    wide = OptimizerPolicy(budget=90, sigma0=0.3, population=None)
    report = pool_grader.practice_report(
        [public], oracle([public]), wide, HONESTY, **kwargs
    )
    assert report["schema"] == "carbon.pool-grade.practice.v1"
    assert report["pool_digests"] == [public.digest]
    assert report["legs"] == {
        "A": 0.9,
        "A_gen": 1.0,
        "A_combined": 0.9,
        "D_opt": 1.0,
        "C": 0.8,
    }
    assert report["total"] == pytest.approx(
        0.5 * 0.9 + 0.5 * 0.8
    )  # D = min(D, C) = 0.8
    assert report["minimums"] == {"A": 0.5} and report["gates"][0]["passed"] is True
    (row,) = report["targets"]
    assert (
        row["d"] == 1.0
        and row["feasible"]
        and row["reached_reference"]
        and row["reason"] == "graded"
    )
    kwargs["gates"] = [{"code": "physics_contract", "passed": False}]
    failed = pool_grader.practice_report(
        [public], oracle([public]), wide, HONESTY, **kwargs
    )
    assert (
        failed["total"] == 0.0 and failed["legs"]["D_opt"] == 1.0
    ), "a failed mandatory gate gives no score"


def exact_target(u_e=0.0, bound_e=0.35, seed=3):
    """The toy plus an exactly computed output e = x * y (an analytic quantity: U = 0) with its own limit."""
    rng = random.Random(seed)
    points = [(rng.random(), rng.random()) for _ in range(60)]
    points += [
        (0.6 + rng.uniform(-0.1, 0.1), 0.6 + rng.uniform(-0.1, 0.1)) for _ in range(40)
    ]
    truths = [{**outputs_of(x, y), "e": x * y} for x, y in points]
    return build_target(
        target_id="ex",
        conditions={"case": "ex"},
        outputs=("f", "g", "e"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", 0.8), Limit("e", "<=", bound_e)),
        u={"f": U, "g": U, "e": u_e},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=[list(p) for p in points],
        truths=truths,
        agen=(),
        start=(0.5, 0.5),
        seed=seed,
    )


def test_an_exactly_computed_output_has_u_zero_and_is_held_to_equality():
    spec = exact_target()
    table = {(spec.conditions["case"], d): t for d, t in zip(spec.designs, spec.truths)}

    def model(shift=0.0):
        def predict(conditions, designs):
            return [
                {
                    **table[(conditions["case"], tuple(d))],
                    "e": table[(conditions["case"], tuple(d))]["e"] + shift,
                }
                for d in designs
            ]

        return predict

    wide = OptimizerPolicy(budget=90, sigma0=0.3, population=None)
    good = grade_target(spec, model(), wide, HONESTY)
    assert good.reason == "graded" and good.h == 1.0 and good.e == 0.0
    # The exact output does not enter the honesty scale when it matches; a mismatch is a wiring fault: h = 0.
    broken = grade_target(spec, model(0.001), wide, HONESTY)
    assert broken.h == 0.0 and broken.d == 0.0
    # U = 0 everywhere, or a negative U, is refused.
    with pytest.raises(PoolRefused, match="u_needs_one_predicted_output"):
        build_target(**{**_exact_kwargs(), "u": {"f": 0.0, "g": 0.0, "e": 0.0}})
    with pytest.raises(PoolRefused, match="u_must_be_non_negative"):
        build_target(**{**_exact_kwargs(), "u": {"f": U, "g": U, "e": -1.0}})


def _exact_kwargs():
    spec = exact_target()
    return {
        "target_id": "ex",
        "conditions": {"case": "ex"},
        "outputs": ("f", "g", "e"),
        "objective": "f",
        "sense": "max",
        "limits": spec.limits,
        "u": spec.u,
        "box": ((0.0, 1.0), (0.0, 1.0)),
        "designs": [list(d) for d in spec.designs],
        "truths": list(spec.truths),
        "agen": (),
        "start": (0.5, 0.5),
        "seed": 3,
    }


def test_a_predicted_violation_of_an_exact_limit_ranks_before_a_u_normalised_one():
    spec = exact_target(bound_e=0.30)
    base = {(d,): t for d, t in zip(map(tuple, spec.designs), spec.truths)}

    def optimistic_on_g(conditions, designs):
        # claims g is safe everywhere but reports the exact output truthfully: only e can make a point infeasible
        return [{**base[(tuple(d),)], "g": 0.0} for d in designs]

    wide = OptimizerPolicy(budget=90, sigma0=0.3, population=None)
    grade = grade_target(spec, optimistic_on_g, wide, HONESTY)
    # Every pick must respect the exact limit e <= 0.30 (the model reports e exactly): it is never infeasible on e.
    assert grade.pick is None or spec.truths[grade.pick]["e"] <= 0.30


def relative_target(rel=0.03, extra=(), seed=3):
    """A Cooling-like target: output h (like hydraulic power, limit h <= 0.25) with U = 3 % of each row's own h."""
    rng = random.Random(seed)
    points = [(rng.random(), rng.random()) for _ in range(60)]
    points += [
        (0.6 + rng.uniform(-0.1, 0.1), 0.6 + rng.uniform(-0.1, 0.1)) for _ in range(40)
    ]
    points += list(extra)
    truths = [{"f": x + y, "h": 0.1 + 0.2 * (x * x + y * y) / 2.0} for x, y in points]
    return build_target(
        target_id="rel",
        conditions={"case": "rel"},
        outputs=("f", "h"),
        objective="f",
        sense="max",
        limits=(Limit("h", "<=", 0.25),),
        u={"f": U, "h": {"relative": rel}},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=[list(p) for p in points],
        truths=truths,
        agen=(),
        start=(0.5, 0.5),
        seed=seed,
    )


def test_a_relative_u_is_r_times_each_rows_own_value_and_is_never_a_scalar():
    spec = relative_target()
    assert spec.u["h"] == {
        "relative": 0.03
    }, "kept as a relative U, never turned into a number"
    for index in (0, 5, 40):
        assert spec.u_at(index, "h") == pytest.approx(
            0.03 * abs(spec.truths[index]["h"])
        )
        assert spec.u_at(index, "f") == U
    # Never read as an absolute 0.03 W: a row near h = 0.25 has U about 0.0075, a row near 0.1 about 0.003.
    assert pool_grader.u_value({"relative": 0.03}, 0.25) == pytest.approx(0.0075)
    assert pool_grader.u_value({"relative": 0.03}, 0.1) == pytest.approx(0.003)
    assert pool_grader.u_value(0.03, 0.25) == 0.03


def _with_extra_row(h, u_h):
    rng = random.Random(3)
    points = [(rng.random(), rng.random()) for _ in range(60)]
    points += [
        (0.6 + rng.uniform(-0.1, 0.1), 0.6 + rng.uniform(-0.1, 0.1)) for _ in range(40)
    ]
    truths = [{"f": x + y, "h": 0.1 + 0.2 * (x * x + y * y) / 2.0} for x, y in points]

    def build(extra):
        return build_target(
            target_id="rel",
            conditions={"case": "rel"},
            outputs=("f", "h"),
            objective="f",
            sense="max",
            limits=(Limit("h", "<=", 0.25),),
            u={"f": U, "h": u_h},
            box=((0.0, 1.0), (0.0, 1.0)),
            designs=[list(p) for p in points] + ([[0.5, 0.5]] if extra else []),
            truths=[*truths, {"f": 1.0, "h": h}] if extra else truths,
            agen=(),
            start=(0.5, 0.5),
            seed=3,
        )

    return build(True).excluded - build(False).excluded


def test_the_exclusion_uses_three_percent_of_the_rows_own_value():
    relative = {"relative": 0.03}
    # h = 0.2425: margin 0.0075 > 3 % of its own value (0.007275): just OUTSIDE, kept.
    assert _with_extra_row(0.2425, relative) == 0
    # h = 0.2428: margin 0.0072 <= 3 % of its own value (0.007284): just INSIDE, excluded.
    assert _with_extra_row(0.2428, relative) == 1
    # Read as an absolute 0.0075 (3 % of the limit, the wrong rule) the row h = 0.2426 would be excluded:
    # a relative U is never a scalar.
    assert _with_extra_row(0.2426, relative) == 0
    assert _with_extra_row(0.2426, 0.0075) == 1


def test_relative_u_drives_the_grader_and_is_refused_when_malformed():
    spec = relative_target()
    table = {(spec.conditions["case"], d): t for d, t in zip(spec.designs, spec.truths)}

    def model(conditions, designs):
        return [dict(table[(conditions["case"], tuple(d))]) for d in designs]

    wide = OptimizerPolicy(budget=90, sigma0=0.3, population=None)
    good = grade_target(spec, model, wide, HONESTY)
    assert good.reason == "graded" and good.h == 1.0 and good.d == pytest.approx(1.0)

    def off(conditions, designs):
        # an error of 3 % of the row's own h (one U) on h only
        return [{**t, "h": t["h"] * 1.03} for t in model(conditions, designs)]

    shifted = grade_target(spec, off, wide, HONESTY)
    assert shifted.e == pytest.approx(1.0, rel=1e-6) or shifted.reason != "graded"
    kwargs = {
        "target_id": "rel",
        "conditions": {"case": "rel"},
        "outputs": ("f", "h"),
        "objective": "f",
        "sense": "max",
        "limits": spec.limits,
        "box": ((0.0, 1.0), (0.0, 1.0)),
        "designs": [list(d) for d in spec.designs],
        "truths": list(spec.truths),
        "agen": (),
        "start": (0.5, 0.5),
        "seed": 3,
    }
    for bad in (
        {"relative": 0.0},
        {"relative": -1.0},
        {"relative": 0.03, "extra": 1},
        {"rel": 0.03},
    ):
        with pytest.raises(PoolRefused, match="u_must_be_non_negative"):
            build_target(**kwargs, u={"f": U, "h": bad})
    # A custody document with a relative U loads through spec_from_source-style kwargs unchanged.
    assert pool_grader.dump_pool(spec)["u"]["h"] == {"relative": 0.03}


def test_the_ood_shell_is_the_outer_half_of_the_approved_extension_and_inside_train_is_never_in_it():
    from carbon.scoring.pool_grader import in_ood_shell

    # TRAIN 0.2..0.8; approved extension 0.25 above (shell 0.925..1.05) and 0.1 below (shell 0.1..0.15).
    shell = ((0.2, 0.8, 0.1, 0.25),)
    inside = [0.5, 0.2, 0.8]
    inner_half = [0.9, 0.17, 0.925 - 1e-3]
    shell_points = [0.93, 1.05, 0.1, 0.15, 0.925]
    beyond = [1.06, 0.09]
    assert not any(in_ood_shell([x], shell) for x in inside + inner_half + beyond)
    assert all(in_ood_shell([x], shell) for x in shell_points)
    # An input with no approved extension contributes nothing; the 12.5 % fallback halves the shell.
    assert not in_ood_shell([1.5], ((0.2, 0.8, 0.0, 0.0),))
    assert in_ood_shell([0.8 + 0.07], ((0.2, 0.8, 0.0, 0.125),))
    assert not in_ood_shell([0.8 + 0.06], ((0.2, 0.8, 0.0, 0.125),))
    # One input in the shell is enough.
    assert in_ood_shell([0.5, 0.93], ((0.2, 0.8, 0.1, 0.25), (0.2, 0.8, 0.1, 0.25)))


def _shelled(shell, seed=3, in_shell=True, fixed=None):
    rng = random.Random(seed)
    if in_shell:
        points = [(rng.uniform(0.6, 1.0), rng.uniform(0.6, 1.0)) for _ in range(100)]
    else:
        points = [(rng.random(), rng.random()) for _ in range(100)]
    return build_target(
        target_id="x",
        conditions={"case": "x", "fixed": fixed if fixed is not None else {}},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", 1.2),),
        u={"f": U, "g": U},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=[list(p) for p in points],
        truths=[outputs_of(*p) for p in points],
        agen=(),
        start=(0.5, 0.5),
        seed=seed,
        shell=shell,
    )


DESIGN_SHELL = {
    "mode": "designs",
    "inputs": ((0.1, 0.2, 0.0, 0.8), (0.1, 0.2, 0.0, 0.8)),
}


def test_an_extended_target_stops_unless_every_queryable_point_is_in_its_shell():
    registered = _shelled(None, in_shell=False)
    assert not registered.extended and registered.shell is None
    extended = _shelled(DESIGN_SHELL)
    assert extended.extended and extended.shell["mode"] == "designs"
    assert (
        extended.digest != _shelled(None).digest
    ), "the shell is part of the pool's identity"
    # A pool that spreads over the whole box has points inside TRAIN: the payload and the grader disagree: STOP.
    with pytest.raises(PoolRefused, match="outside_the_ood_shell|reference_not_in"):
        _shelled(DESIGN_SHELL, in_shell=False)
    # A shell the reference is not in (here the extension is too short for any point) is a STOP.
    short = {"mode": "designs", "inputs": ((0.1, 0.2, 0.0, 0.2), (0.1, 0.2, 0.0, 0.2))}
    with pytest.raises(PoolRefused, match="reference_not_in_the_ood_shell"):
        _shelled(short)
    # The mode is explicit, never inferred: a bare list, a bad mode, a wrong width or a bad row are refused.
    with pytest.raises(PoolRefused, match="shell_must_be_a_mode"):
        _shelled(((0.1, 0.2, 0.0, 0.8), (0.1, 0.2, 0.0, 0.8)))
    with pytest.raises(PoolRefused, match="shell_mode_must_be"):
        _shelled({"mode": "inferred", "inputs": ()})
    with pytest.raises(PoolRefused, match="shell_needs_one_row_per_design_input"):
        _shelled({"mode": "designs", "inputs": ((0.1, 0.2, 0.0, 0.8),)})
    with pytest.raises(PoolRefused, match="shell_rows_are"):
        _shelled(
            {"mode": "designs", "inputs": ((0.2, 0.1, 0.0, 0.8), (0.1, 0.2, 0.0, 0.8))}
        )
    # The shell survives the pool document round trip and a tampered shell fails the digest.
    import json

    document = json.loads(json.dumps(pool_grader.dump_pool(extended)))
    assert pool_grader.load_pool(document).shell == extended.shell
    document["shell"]["inputs"][0][3] = 0.9
    with pytest.raises(PoolRefused, match="digest"):
        pool_grader.load_pool(document)


def test_a_conditions_shell_checks_the_fixed_conditions_once_and_leaves_the_design_free():
    # TRAIN 0.0..0.5 on the condition `cond`, extension 1.0 above: its shell is 1.0..1.5.
    shell = {"mode": "conditions", "inputs": {"cond": (0.0, 0.5, 0.0, 1.0)}}
    in_range = _shelled(shell, in_shell=False, fixed={"cond": 1.2})
    assert in_range.extended and in_range.shell["mode"] == "conditions"
    with pytest.raises(PoolRefused, match="conditions_not_in_the_ood_shell"):
        _shelled(shell, in_shell=False, fixed={"cond": 0.7})
    with pytest.raises(PoolRefused, match="names_must_be_fixed_conditions"):
        _shelled(shell, in_shell=False, fixed={"other": 1.2})
    with pytest.raises(PoolRefused, match="needs_a_row_per_condition_name"):
        _shelled(
            {"mode": "conditions", "inputs": {}}, in_shell=False, fixed={"cond": 1.2}
        )
    import json

    document = json.loads(json.dumps(pool_grader.dump_pool(in_range)))
    assert pool_grader.load_pool(document).shell == in_range.shell

"""Multi-class balanced regions of the pool grader (new exam versions only; Validator ruling, the multi-class balanced-regions
build).

Claims: a target's class comes only from the version's registered coverage plan (target id -> class name, the plan's class
order), never from code or a model; with ``balanced_region_mean`` a set's D, and with the new ``a_gen_aggregate`` a set's
A_gen, are the mean over the plan's classes of each class's mean, so a small class cannot be averaged away; a target
missing from the plan is refused, never defaulted to in_train; the plan binds by its registered sha256; every registered
version (no aggregate, no plan) is unchanged. Every class name, count and value here is a SYNTHETIC fixture: none is a
production class list, digest, scale or threshold.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
from types import SimpleNamespace

import pytest

from carbon.scoring import pool_exam, pool_grader, pool_version
from carbon.scoring import pool_proof_suite as suite
from carbon.scoring.pool_grader import (
    CoveragePlan,
    OptimizerPolicy,
    PoolRefused,
    TargetGrade,
    agen_accuracy,
    coverage_plan,
    grade_set,
)
from tests.cpu.test_pool_grader import HONESTY, OPTIMIZER, oracle, toy_target

# Synthetic class names: deliberately not any registered plan's names.
BIG, MID, SMALL = "fixture:big", "fixture:mid", "fixture:small"
SCALES = {"f": 0.1, "g": 0.1}


def plan_document(classes, targets):
    return {
        "schema": pool_grader.COVERAGE_PLAN_SCHEMA,
        "classes": list(classes),
        "targets": dict(targets),
    }


def three_class_plan(n_big, n_mid=2, n_small=1, order=(BIG, MID, SMALL)):
    targets = {}
    for name, count in ((BIG, n_big), (MID, n_mid), (SMALL, n_small)):
        targets.update({f"{name.split(':')[1]}{i}": name for i in range(count)})
    return coverage_plan(plan_document(order, targets))


def balanced(plan, **fields):
    return dataclasses.replace(
        OPTIMIZER,
        d_aggregate="balanced_region_mean",
        coverage_plan_sha256=plan.sha256,
        coverage_plan=plan,
        **fields,
    )


def stand_ins(monkeypatch, ds):
    """Targets whose grade is the chosen d (the grader's own per-target arithmetic is not under test here)."""
    specs = [SimpleNamespace(target_id=t, extended=False) for t in ds]
    graded = []

    def grade(spec, predict, optimizer, honesty):
        graded.append(spec.target_id)
        d = ds[spec.target_id]
        return TargetGrade(
            spec.target_id, "sha256:x", d, d, 1.0, 0.0, True, 0, 1, "graded", False
        )

    monkeypatch.setattr(pool_grader, "grade_target", grade)
    return specs, graded


# --- D -----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("n_big", [6, 60])
def test_a_small_class_cannot_be_averaged_away_in_d(monkeypatch, n_big):
    plan = three_class_plan(n_big)
    ds = {t: (0.0 if c == SMALL else 1.0) for t, c in plan.targets}
    specs, _ = stand_ins(monkeypatch, ds)
    plain = grade_set(specs, None, OPTIMIZER, HONESTY)
    result = grade_set(specs, None, balanced(plan), HONESTY)
    assert plain.d == pytest.approx((n_big + 2) / (n_big + 3))
    # the mean of the class means 1.0, 1.0 and 0.0, however many big-class targets there are
    assert result.d == pytest.approx(2 / 3)
    assert result.regions == ((BIG, 1.0), (MID, 1.0), (SMALL, 0.0))


def test_the_class_order_is_the_plans_and_each_class_is_its_own_mean(monkeypatch):
    order = (SMALL, BIG, MID)
    plan = three_class_plan(3, order=order)
    values = {BIG: [0.9, 0.6, 0.3], MID: [0.8, 0.4], SMALL: [0.1]}
    ds = {}
    for name in (BIG, MID, SMALL):
        ids = [t for t, c in plan.targets if c == name]
        ds.update(zip(ids, values[name], strict=True))
    specs, _ = stand_ins(monkeypatch, ds)
    result = grade_set(specs, None, balanced(plan), HONESTY)
    assert [name for name, _ in result.regions] == list(order)
    assert dict(result.regions) == pytest.approx({BIG: 0.6, MID: 0.6, SMALL: 0.1})
    assert result.d == pytest.approx((0.6 + 0.6 + 0.1) / 3)
    assert set(result.public()) == {"d", "reasons"}  # no class leaves custody


def test_a_class_with_no_target_in_the_set_is_skipped(monkeypatch):
    plan = three_class_plan(2)
    ds = {t: 0.5 for t, c in plan.targets if c != MID}
    specs, _ = stand_ins(monkeypatch, ds)
    result = grade_set(specs, None, balanced(plan), HONESTY)
    assert [name for name, _ in result.regions] == [BIG, SMALL]


def test_a_single_class_plan_is_the_plain_mean_bit_for_bit():
    specs = [toy_target(f"t{i}", seed=i) for i in range(3)]
    plan = coverage_plan(plan_document([BIG], {s.target_id: BIG for s in specs}))
    predict = oracle(specs)

    def off(conditions, designs):
        return [
            {"f": t["f"] + 0.03 * (1 + len(conditions["case"])), "g": t["g"]}
            for t in predict(conditions, designs)
        ]

    policy = balanced(plan, a_gen_aggregate="balanced_region_mean")
    assert (
        grade_set(specs, off, policy, HONESTY).d
        == grade_set(specs, off, OPTIMIZER, HONESTY).d
    )
    assert agen_accuracy(
        specs, off, SCALES, aggregate="balanced_region_mean", plan=plan
    ) == agen_accuracy(specs, off, SCALES)


# --- A_gen -------------------------------------------------------------------------------------------------------------


def agen_targets(n_big):
    specs = [toy_target(f"big{i}", seed=i) for i in range(n_big)]
    specs += [toy_target(f"mid{i}", seed=50 + i) for i in range(2)]
    specs += [toy_target("small0", seed=90)]
    return specs


def small_class_misses(specs):
    """The oracle, except the small class's target, whose f is 0.9 off (synthetic): its A_gen is 0.5 * (1/(1+9) + 1)."""
    base = oracle(specs)

    def predict(conditions, designs):
        rows = base(conditions, designs)
        if conditions["case"].startswith("small"):
            return [{"f": r["f"] + 0.9, "g": r["g"]} for r in rows]
        return rows

    return predict


@pytest.mark.parametrize("n_big", [3, 12])
def test_a_small_class_cannot_be_averaged_away_in_a_gen(n_big):
    specs = agen_targets(n_big)
    plan = three_class_plan(n_big)
    predict = small_class_misses(specs)
    small = 0.5 * (0.1 + 1.0)
    per_target = [agen_accuracy([s], predict, SCALES) for s in specs]
    assert per_target[-1] == pytest.approx(small) and set(per_target[:-1]) == {1.0}
    plain = agen_accuracy(specs, predict, SCALES)
    value = agen_accuracy(
        specs, predict, SCALES, aggregate="balanced_region_mean", plan=plan
    )
    assert plain == pytest.approx((n_big + 2 + small) / (n_big + 3))
    assert value == pytest.approx((1.0 + 1.0 + small) / 3)
    assert value < plain


def test_a_gen_skips_a_target_without_a_slice_and_a_class_without_one():
    specs = [toy_target("big0", seed=1), toy_target("mid0", seed=2, agen_count=0)]
    specs.append(toy_target("small0", seed=3))
    plan = coverage_plan(
        plan_document([BIG, MID, SMALL], {"big0": BIG, "mid0": MID, "small0": SMALL})
    )
    predict = small_class_misses(specs)
    value = agen_accuracy(
        specs, predict, SCALES, aggregate="balanced_region_mean", plan=plan
    )
    assert value == pytest.approx((1.0 + 0.5 * (0.1 + 1.0)) / 2)


def test_the_balanced_a_gen_needs_a_plan_and_a_known_aggregate():
    specs = [toy_target()]
    with pytest.raises(PoolRefused, match="needs_a_registered_coverage_plan"):
        agen_accuracy(specs, oracle(specs), SCALES, aggregate="balanced_region_mean")
    with pytest.raises(PoolRefused, match="a_gen_aggregate_must_be"):
        agen_accuracy(specs, oracle(specs), SCALES, aggregate="mean")


def test_the_practice_report_uses_the_registered_a_gen_aggregate():
    specs = [dataclasses.replace(s, public=True) for s in agen_targets(3)]
    plan = three_class_plan(3)
    predict = small_class_misses(specs)
    common = {
        "a": 0.5,
        "c": 1.0,
        "a_rule": {"kind": "mean"},
        "agen_scales": SCALES,
        "c_rule": {"kind": "min"},
    }
    plain = pool_grader.practice_report(specs, predict, OPTIMIZER, HONESTY, **common)
    new = pool_grader.practice_report(
        specs,
        predict,
        balanced(plan, a_gen_aggregate="balanced_region_mean"),
        HONESTY,
        **common,
    )
    assert plain["legs"]["A_gen"] == agen_accuracy(specs, predict, SCALES)
    assert new["legs"]["A_gen"] == agen_accuracy(
        specs, predict, SCALES, aggregate="balanced_region_mean", plan=plan
    )


# --- a target missing from the plan ------------------------------------------------------------------------------------


def test_a_target_missing_from_the_plan_is_refused_before_anything_is_graded(
    monkeypatch,
):
    plan = three_class_plan(2)
    ds = {t: 1.0 for t, _c in plan.targets}
    ds["stray"] = 1.0
    specs, graded = stand_ins(monkeypatch, ds)
    for policy in (
        balanced(plan),
        dataclasses.replace(balanced(plan), d_aggregate=None),
    ):
        with pytest.raises(PoolRefused, match="target_not_in_the_coverage_plan"):
            grade_set(specs, None, policy, HONESTY)
    assert graded == []


def test_a_missing_target_is_never_defaulted_to_in_train():
    plan = three_class_plan(1)
    stray = SimpleNamespace(target_id="stray", extended=False)
    assert pool_grader.region_class(stray) == "in_train"  # the 2-class fallback only
    with pytest.raises(PoolRefused, match="target_not_in_the_coverage_plan"):
        pool_grader.region_class(stray, plan)
    calls = []

    def predict(conditions, designs):
        calls.append(conditions)
        return []

    specs = [toy_target("big0"), toy_target("stray")]
    with pytest.raises(PoolRefused, match="target_not_in_the_coverage_plan"):
        agen_accuracy(
            specs, predict, SCALES, aggregate="balanced_region_mean", plan=plan
        )
    assert calls == []


# --- the plan and its registration ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "document",
    [
        None,
        {"classes": [BIG], "targets": {"t": BIG}},
        {"schema": "x", "classes": [BIG], "targets": {"t": BIG}},
        plan_document([], {"t": BIG}),
        plan_document([BIG, BIG], {"t": BIG}),
        plan_document([BIG, ""], {"t": BIG}),
        plan_document([BIG], {}),
        plan_document([BIG], {"t": MID}),
        plan_document([BIG], {"": BIG}),
        plan_document([BIG, MID], {"t": BIG}),  # a listed class without a target
        {**plan_document([BIG], {"t": BIG}), "extra": 1},
    ],
)
def test_a_malformed_plan_is_refused(document):
    with pytest.raises(PoolRefused):
        coverage_plan(document)


def test_the_plan_binds_by_the_sha256_of_its_canonical_document():
    document = plan_document([BIG, SMALL], {"a": BIG, "b": SMALL})
    plan = coverage_plan(document)
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    assert plan.sha256 == hashlib.sha256(canonical.encode()).hexdigest()
    reordered = coverage_plan(plan_document([SMALL, BIG], {"a": BIG, "b": SMALL}))
    assert reordered.sha256 != plan.sha256  # the class order is part of the identity
    assert plan.classes == (BIG, SMALL) and plan.targets == (("a", BIG), ("b", SMALL))


def test_an_attached_plan_must_be_the_registered_one(monkeypatch):
    plan = three_class_plan(1)
    other = three_class_plan(2)
    specs, _ = stand_ins(monkeypatch, {t: 1.0 for t, _c in plan.targets})
    cases = [
        (dataclasses.replace(balanced(plan), coverage_plan=other), "registered_one"),
        (
            dataclasses.replace(balanced(plan), coverage_plan_sha256=None),
            "registered_one",
        ),
        (dataclasses.replace(balanced(plan), coverage_plan=None), "not_attached"),
        (dataclasses.replace(balanced(plan), coverage_plan_sha256="ab"), "64_hex"),
        (
            dataclasses.replace(OPTIMIZER, a_gen_aggregate="balanced_region_mean"),
            "needs",
        ),
        (dataclasses.replace(OPTIMIZER, a_gen_aggregate="mean"), "a_gen_aggregate"),
    ]
    for policy, code in cases:
        with pytest.raises(PoolRefused, match=code):
            grade_set(specs, None, policy, HONESTY)


def _entry(**optimizer):
    return {
        "optimizer": {"budget": 40, "sigma0": 0.3, "population": 8, **optimizer},
        "honesty": {"scale": 1.0, "reduction": "max"},
        "agen_scales": {"x": 1.0},
        "a_rule": {"kind": "mean"},
        "c_rule": {"kind": "min"},
    }


def _policies(tmp_path, entry):
    path = tmp_path / "pool_constants.json"
    path.write_text(
        json.dumps(
            {"schema": pool_version.SCHEMA, "versions": {"fixture-x 9.9": entry}}
        )
    )
    return pool_version.registered_policies("fixture-x", "9.9", path=path)


def test_the_registration_reads_both_fields_with_no_default_when_present(tmp_path):
    sha = three_class_plan(1).sha256
    absent = _policies(tmp_path, _entry()).optimizer
    assert absent.a_gen_aggregate is None and absent.coverage_plan_sha256 is None
    new = _policies(
        tmp_path,
        _entry(
            d_aggregate="balanced_region_mean",
            a_gen_aggregate="balanced_region_mean",
            coverage_plan_sha256=sha,
        ),
    ).optimizer
    assert new.a_gen_aggregate == "balanced_region_mean"
    assert new.coverage_plan_sha256 == sha and new.coverage_plan is None
    for fields, error in [
        ({"a_gen_aggregate": pool_version.HUMAN_INPUT}, "not_registered"),
        ({"coverage_plan_sha256": pool_version.HUMAN_INPUT}, "not_registered"),
        ({"a_gen_aggregate": None}, "malformed"),
        ({"coverage_plan_sha256": None}, "malformed"),
        ({"coverage_plan_sha256": sha.upper()}, "malformed"),
        ({"coverage_plan_sha256": "sha256:" + sha}, "malformed"),
        ({"a_gen_aggregate": "balanced_region_mean"}, "malformed"),  # no plan
        ({"a_gen_aggregate": "mean", "coverage_plan_sha256": sha}, "malformed"),
    ]:
        with pytest.raises(pool_version.PoolConstantsNotRegistered, match=error):
            _policies(tmp_path, _entry(**fields))


def test_every_registered_version_registers_no_plan_and_no_a_gen_aggregate():
    assert (
        OptimizerPolicy(budget=5, sigma0=0.3, population=None).a_gen_aggregate is None
    )
    document = json.loads(pool_version.CONSTANTS.read_bytes())
    for name, entry in document["versions"].items():
        assert "a_gen_aggregate" not in entry["optimizer"], name
        assert "coverage_plan_sha256" not in entry["optimizer"], name
        challenge, version = name.rsplit(" ", 1)
        try:
            policies = pool_version.registered_policies(challenge, version)
        except pool_version.PoolConstantsNotRegistered:
            continue
        assert policies.optimizer.a_gen_aggregate is None, name
        assert policies.optimizer.coverage_plan_sha256 is None, name


def test_no_coverage_class_name_is_typed_in_the_grader():
    source = inspect.getsource(pool_grader)
    assert "regime:" not in source and "inner_band" not in source


# --- the sealed material ---------------------------------------------------------------------------------------------------


def _policy_set(**optimizer):
    return suite.Policies(
        optimizer=dataclasses.replace(OPTIMIZER, **optimizer),
        honesty=HONESTY,
        agen_scales=SCALES,
        a_rule={"kind": "mean"},
        c_rule={"kind": "min"},
    )


def test_the_material_plan_attaches_only_when_registered_and_complete():
    specs = [toy_target("big0", seed=1), toy_target("small0", seed=2)]
    document = plan_document([BIG, SMALL], {"big0": BIG, "small0": SMALL})
    plan = coverage_plan(document)
    sets = (tuple(specs),)
    unregistered = _policy_set()
    assert pool_version.with_coverage_plan(unregistered, {}, sets) is unregistered
    with pytest.raises(pool_exam.ExamRefused, match="coverage_plan_not_registered"):
        pool_version.with_coverage_plan(unregistered, {"coverage_plan": document}, sets)
    registered = _policy_set(
        d_aggregate="balanced_region_mean", coverage_plan_sha256=plan.sha256
    )
    attached = pool_version.with_coverage_plan(
        registered, {"coverage_plan": document}, sets
    )
    assert attached.optimizer.coverage_plan == plan
    with pytest.raises(pool_exam.ExamRefused, match="missing_from_the_sealed_pack"):
        pool_version.with_coverage_plan(registered, {}, sets)
    with pytest.raises(pool_exam.ExamRefused, match="coverage_plan_malformed"):
        pool_version.with_coverage_plan(
            registered, {"coverage_plan": {**document, "schema": "x"}}, sets
        )
    other = plan_document([SMALL, BIG], {"big0": BIG, "small0": SMALL})
    with pytest.raises(pool_exam.ExamRefused, match="sha256_mismatch"):
        pool_version.with_coverage_plan(registered, {"coverage_plan": other}, sets)
    short = plan_document([BIG], {"big0": BIG})
    short_registered = _policy_set(coverage_plan_sha256=coverage_plan(short).sha256)
    with pytest.raises(pool_exam.ExamRefused, match="target_not_in_the_coverage_plan"):
        pool_version.with_coverage_plan(
            short_registered, {"coverage_plan": short}, sets
        )


def test_the_material_check_admits_a_valid_plan_and_refuses_a_malformed_one():
    material = {
        "schema": pool_version.MATERIAL_SCHEMA,
        "kind": "fixture",
        "version": "9.9",
        "input_names": ["x"],
        "design_names": ["x"],
        "input_dtype": "float32",
        "set_digest": "sha256:fixture",
        "sets": [[{}]],
    }
    assert pool_version.check_material(material) is material
    good = {**material, "coverage_plan": plan_document([BIG], {"t": BIG})}
    assert pool_version.check_material(good) is good
    with pytest.raises(pool_exam.ExamRefused, match="pool_material_malformed"):
        pool_version.check_material(
            {**material, "coverage_plan": plan_document([BIG], {"t": MID})}
        )


def test_the_exam_path_refuses_a_registered_a_gen_aggregate(monkeypatch):
    """`pool_proof_suite.score_specs` computes the plain A_gen, so a version that registers the class-balanced one refuses to
    grade (Carbon's gap) instead of being graded by the plain mean."""
    plan = three_class_plan(1)
    policies = _policy_set(
        a_gen_aggregate="balanced_region_mean", coverage_plan_sha256=plan.sha256
    )
    monkeypatch.setattr(pool_version, "registered_policies", lambda c, v: policies)
    monkeypatch.setattr(
        pool_grader,
        "load_pool",
        lambda document: pytest.fail("graded past the refusal"),
    )
    adapter = SimpleNamespace(_challenge_id="fixture-x", VERSION="9.9")
    with pytest.raises(
        pool_exam.ExamRefused, match="a_gen_aggregate_not_in_the_exam_path"
    ):
        pool_version.PoolVariant.measure(
            adapter,
            bank_rows=[],
            outputs=[],
            repeats=[],
            definition={"pool": {"sets": [[{}]]}},
            limits=None,
            objective=None,
            train_raw=None,
            names=None,
        )


def test_a_plan_is_a_frozen_value():
    plan = three_class_plan(1)
    assert isinstance(plan, CoveragePlan)
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.classes = ()

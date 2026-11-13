"""Multi-class balanced regions of the pool grader (new exam versions only; Validator rulings on the multi-class
balanced-regions build).

Claims: a target's class comes only from the version's registered coverage plan (target id -> class name, the plan's class
order), never from code or a model; with ``balanced_region_mean`` a set's D, and with the new ``a_gen_aggregate`` a set's
A_gen, are the mean over the plan's classes of each class's mean, so a small class cannot be averaged away; a target missing
from the plan, or a set missing a registered class, is refused, never defaulted or skipped; the plan binds by its registered
sha256 AND by the registered sha256 of the plan package's SHA256SUMS, which must list it; the exam path (score_specs, the
SE basis and its bootstrap) aggregates exactly as the grade; class names must be geometric-v1 names, and until the rule's
vocabulary is in the repository every plan is refused; every registered version (no aggregate, no plan) is unchanged.
Every class name, count and value here is a SYNTHETIC fixture: none is a production class list, digest, scale or threshold.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_pool_exam import ARGUMENTS, CEILING, FAST, POLICIES, exam_rows, toy_binding
from test_pool_plugin import fake_measure, good_serve
from test_pool_plugin import toy_target as exam_target

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
KEY = "sha256:" + "ab" * 32


def plan_document(classes, targets):
    return {
        "schema": pool_grader.COVERAGE_PLAN_SCHEMA,
        "classes": list(classes),
        "targets": dict(targets),
    }


def sums_text(*shas):
    """A synthetic SHA256SUMS listing the given digests (the `sha256sum` line format)."""
    return "".join(f"{sha} *./file-{n}.json\n" for n, sha in enumerate(shas))


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


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
        coverage_plan_sums_sha256=sha(sums_text(plan.sha256)),
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


def test_a_set_missing_a_registered_class_is_refused_never_skipped(monkeypatch):
    plan = three_class_plan(2)
    ds = {t: 0.5 for t, c in plan.targets if c != MID}
    specs, graded = stand_ins(monkeypatch, ds)
    for policy in (
        balanced(plan),
        dataclasses.replace(balanced(plan), d_aggregate=None),
    ):
        with pytest.raises(PoolRefused, match="set_missing_a_registered_class"):
            grade_set(specs, None, policy, HONESTY)
    assert graded == []


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


def small_class_misses(specs, key="case"):
    """The oracle, except the small class's target, whose f is 0.9 off (synthetic): its A_gen is 0.5 * (1/(1+9) + 1)."""
    base = oracle(specs)

    def predict(conditions, designs):
        rows = base(conditions, designs)
        if conditions[key].startswith("small"):
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


def test_a_gen_refuses_a_class_without_a_reserved_slice_before_any_prediction():
    specs = [toy_target("big0", seed=1), toy_target("mid0", seed=2, agen_count=0)]
    specs.append(toy_target("small0", seed=3))
    plan = coverage_plan(
        plan_document([BIG, MID, SMALL], {"big0": BIG, "mid0": MID, "small0": SMALL})
    )
    calls = []

    def predict(conditions, designs):
        calls.append(conditions)
        return oracle(specs)(conditions, designs)

    with pytest.raises(PoolRefused, match="a_gen_class_without_a_reserved_slice"):
        agen_accuracy(
            specs, predict, SCALES, aggregate="balanced_region_mean", plan=plan
        )
    assert calls == []
    # the plain mean on the same plan only needs every class to have a target
    assert agen_accuracy(specs, predict, SCALES, plan=plan) == agen_accuracy(
        specs, predict, SCALES
    )


def test_the_balanced_a_gen_needs_a_plan_and_a_known_aggregate():
    specs = [toy_target()]
    with pytest.raises(PoolRefused, match="needs_a_registered_coverage_plan"):
        agen_accuracy(specs, oracle(specs), SCALES, aggregate="balanced_region_mean")
    with pytest.raises(PoolRefused, match="a_gen_aggregate_must_be"):
        agen_accuracy(specs, oracle(specs), SCALES, aggregate="mean")


def test_agen_for_makes_the_plain_call_for_a_registered_version(monkeypatch):
    """A registered version's A_gen goes through the unchanged 3-argument call (a wrapper with that signature still
    works); a new version's passes its aggregate and plan."""
    seen = []
    real = pool_grader.agen_accuracy

    def three_args(specs, predict, scales):
        seen.append("plain")
        return real(specs, predict, scales)

    specs = agen_targets(1)
    predict = small_class_misses(specs)
    monkeypatch.setattr(pool_grader, "agen_accuracy", three_args)
    assert pool_grader.agen_for(specs, predict, SCALES, OPTIMIZER) == real(
        specs, predict, SCALES
    )
    assert seen == ["plain"]
    monkeypatch.setattr(pool_grader, "agen_accuracy", real)
    plan = three_class_plan(1)
    policy = balanced(plan, a_gen_aggregate="balanced_region_mean")
    assert pool_grader.agen_for(specs, predict, SCALES, policy) == real(
        specs, predict, SCALES, aggregate="balanced_region_mean", plan=plan
    )


def test_score_specs_passes_the_registered_a_gen_aggregate(monkeypatch):
    specs = agen_targets(3)
    plan = three_class_plan(3)
    predict = small_class_misses(specs)
    seen = []

    def agen_for(specs_, predict_, scales, optimizer):
        seen.append(optimizer.a_gen_aggregate)
        return 0.5

    monkeypatch.setattr(pool_grader, "agen_for", agen_for)
    policies = suite.Policies(
        optimizer=balanced(plan, a_gen_aggregate="balanced_region_mean"),
        honesty=HONESTY,
        agen_scales=SCALES,
        a_rule={"kind": "mean"},
        c_rule={"kind": "min"},
    )
    plugin = SimpleNamespace(
        legs=lambda descriptor, specs_: {"A": 0.5, "C": 1.0},
        pool_gates=None,
        speed_gate=None,
    )
    monkeypatch.setattr(suite, "pool_predictor", lambda *a: predict)
    _total, _grade, a_gen, _legs = suite.score_specs(
        plugin, specs, {"kind": "good"}, policies, specs
    )
    assert seen == ["balanced_region_mean"] and a_gen == 0.5


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

    specs = [toy_target(t) for t, _c in plan.targets] + [toy_target("stray")]
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


def test_the_plan_binds_by_the_sha256_of_its_canonical_file():
    document = plan_document([BIG, SMALL], {"a": BIG, "b": SMALL})
    plan = coverage_plan(document)
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    assert pool_grader.coverage_plan_bytes(document) == canonical.encode()
    assert plan.sha256 == sha(canonical)
    reordered = coverage_plan(plan_document([SMALL, BIG], {"a": BIG, "b": SMALL}))
    assert reordered.sha256 != plan.sha256  # the class order is part of the identity
    assert plan.classes == (BIG, SMALL) and plan.targets == (("a", BIG), ("b", SMALL))


def test_the_sums_list_reads_the_sha256sum_format_and_refuses_anything_else():
    a, b = "a" * 64, "b" * 64
    assert pool_grader.sums_list(f"{a} *./x.json\n{b}  y.json\n\n", b)
    assert not pool_grader.sums_list(f"{a} *./x.json\n", b)
    for bad in ["", None, f"{a}*x\n", f"{a.upper()} *x\n", f"{a} *\n", "abc *x\n"]:
        with pytest.raises(PoolRefused, match="coverage_plan_sums_malformed"):
            pool_grader.sums_list(bad, a)


def test_an_attached_plan_must_be_the_registered_one(monkeypatch):
    plan = three_class_plan(1)
    other = three_class_plan(2)
    specs, _ = stand_ins(monkeypatch, {t: 1.0 for t, _c in plan.targets})
    cases = [
        (dataclasses.replace(balanced(plan), coverage_plan=other), "registered_one"),
        (dataclasses.replace(balanced(plan), coverage_plan=None), "not_attached"),
        (dataclasses.replace(balanced(plan), coverage_plan_sha256="ab"), "64_hex"),
        (
            dataclasses.replace(balanced(plan), coverage_plan_sums_sha256="ab"),
            "sums_sha256_must_be_64_hex",
        ),
        (
            dataclasses.replace(balanced(plan), coverage_plan_sums_sha256=None),
            "map_and_sums_digests",
        ),
        (
            dataclasses.replace(
                OPTIMIZER, coverage_plan_sums_sha256=plan.sha256, coverage_plan=plan
            ),
            "map_and_sums_digests",
        ),
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


def test_the_registration_reads_every_field_with_no_default_when_present(tmp_path):
    plan_sha = three_class_plan(1).sha256
    sums_sha = sha(sums_text(plan_sha))
    both = {"coverage_plan_sha256": plan_sha, "coverage_plan_sums_sha256": sums_sha}
    absent = _policies(tmp_path, _entry()).optimizer
    assert absent.a_gen_aggregate is None and absent.coverage_plan_sha256 is None
    assert absent.coverage_plan_sums_sha256 is None
    new = _policies(
        tmp_path,
        _entry(
            d_aggregate="balanced_region_mean",
            a_gen_aggregate="balanced_region_mean",
            **both,
        ),
    ).optimizer
    assert new.a_gen_aggregate == "balanced_region_mean"
    assert new.coverage_plan_sha256 == plan_sha and new.coverage_plan is None
    assert new.coverage_plan_sums_sha256 == sums_sha
    for fields, error in [
        ({"a_gen_aggregate": pool_version.HUMAN_INPUT, **both}, "not_registered"),
        ({**both, "coverage_plan_sha256": pool_version.HUMAN_INPUT}, "not_registered"),
        (
            {**both, "coverage_plan_sums_sha256": pool_version.HUMAN_INPUT},
            "not_registered",
        ),
        ({"a_gen_aggregate": None, **both}, "malformed"),
        ({**both, "coverage_plan_sha256": None}, "malformed"),
        ({**both, "coverage_plan_sums_sha256": None}, "malformed"),
        ({**both, "coverage_plan_sha256": plan_sha.upper()}, "malformed"),
        ({**both, "coverage_plan_sha256": "sha256:" + plan_sha}, "malformed"),
        ({"coverage_plan_sha256": plan_sha}, "malformed"),  # no SUMS digest
        ({"coverage_plan_sums_sha256": sums_sha}, "malformed"),  # no map digest
        ({"a_gen_aggregate": "balanced_region_mean"}, "malformed"),  # no plan
        ({"a_gen_aggregate": "mean", **both}, "malformed"),
    ]:
        with pytest.raises(pool_version.PoolConstantsNotRegistered, match=error):
            _policies(tmp_path, _entry(**fields))


#: The registered NEW versions in the 5 Nov fit-breaker form (mc-exam-B slice 3a, 10 Nov): listed by name, never derived.
_FIVE_NOV_FORM = frozenset({"electric-motor-magnetics 1.8", "chip-cold-plate 1.8"})


def test_every_registered_version_registers_no_plan_and_no_a_gen_aggregate():
    assert (
        OptimizerPolicy(budget=5, sigma0=0.3, population=None).a_gen_aggregate is None
    )
    document = json.loads(pool_version.CONSTANTS.read_bytes())
    for name, entry in document["versions"].items():
        if name in _FIVE_NOV_FORM:
            # a NEW version in the 5 Nov fit-breaker form (test_fit_breaker_conformance): its coverage plan is
            # REQUIRED, its A is the physics block, and it has no A_gen aggregate
            assert "physics" in entry, name
            assert "a_gen_aggregate" not in entry["optimizer"], name
            assert "coverage_plan_sha256" in entry["optimizer"], name
            assert "coverage_plan_sums_sha256" in entry["optimizer"], name
            continue
        for key in (
            "a_gen_aggregate",
            "coverage_plan_sha256",
            "coverage_plan_sums_sha256",
        ):
            assert key not in entry["optimizer"], name
        challenge, version = name.rsplit(" ", 1)
        try:
            policies = pool_version.registered_policies(challenge, version)
        except pool_version.PoolConstantsNotRegistered:
            continue
        assert policies.optimizer.a_gen_aggregate is None, name
        assert policies.optimizer.coverage_plan_sha256 is None, name
        assert policies.optimizer.coverage_plan_sums_sha256 is None, name


def test_no_coverage_class_name_is_typed_in_the_grader_or_the_exam():
    for module in (pool_grader, pool_exam):
        source = inspect.getsource(module)
        assert "regime:" not in source and "inner_band" not in source, module


# --- the sealed material and its attachment -------------------------------------------------------------------------------


def _policy_set(**optimizer):
    return suite.Policies(
        optimizer=dataclasses.replace(OPTIMIZER, **optimizer),
        honesty=HONESTY,
        agen_scales=SCALES,
        a_rule={"kind": "mean"},
        c_rule={"kind": "min"},
    )


@pytest.fixture
def geometric_v1_stand_in(monkeypatch):
    """The receipted geometric-v1 vocabulary is not in the repository; a fixture predicate stands in for it."""
    monkeypatch.setattr(
        pool_exam,
        "geometric_v1_names_valid",
        lambda classes: all(c.startswith("fixture:") for c in classes),
    )


def _plan_and_sums():
    specs = (toy_target("big0", seed=1), toy_target("small0", seed=2))
    document = plan_document([BIG, SMALL], {"big0": BIG, "small0": SMALL})
    plan = coverage_plan(document)
    sums = sums_text("c" * 64, plan.sha256)
    registered = _policy_set(
        d_aggregate="balanced_region_mean",
        coverage_plan_sha256=plan.sha256,
        coverage_plan_sums_sha256=sha(sums),
    )
    return (specs,), document, sums, plan, registered


def test_the_material_plan_attaches_only_when_registered_listed_and_complete(
    geometric_v1_stand_in,
):
    sets, document, sums, plan, registered = _plan_and_sums()
    attach = pool_exam.attach_coverage_plan
    unregistered = _policy_set()
    assert attach(unregistered, None, None, sets) is unregistered
    for doc, text in ((document, sums), (document, None), (None, sums)):
        with pytest.raises(pool_exam.ExamRefused, match="coverage_plan_not_registered"):
            attach(unregistered, doc, text, sets)
    assert attach(registered, document, sums, sets).optimizer.coverage_plan == plan
    refusals = [
        ((None, sums, sets), "coverage_plan_missing_from_the_sealed_pack"),
        ((document, None, sets), "coverage_plan_sums_missing_from_the_sealed_pack"),
        (({**document, "schema": "x"}, sums, sets), "coverage_plan_malformed"),
        ((document, "not a sums file", sets), "coverage_plan_malformed"),
        (
            (plan_document([SMALL, BIG], {"big0": BIG, "small0": SMALL}), sums, sets),
            "coverage_plan_sha256_mismatch",
        ),
        ((document, sums + sums_text("d" * 64), sets), "sums_sha256_mismatch"),
        (
            (document, sums, ((toy_target("big0", seed=1), toy_target("x", seed=3)),)),
            "target_not_in_the_coverage_plan",
        ),
        (
            (document, sums, ((toy_target("big0", seed=1),),)),
            "set_missing_a_registered_class",
        ),
    ]
    for arguments, code in refusals:
        with pytest.raises(pool_exam.ExamRefused, match=code):
            attach(registered, *arguments)
    # a SUMS of the registered digest that does not list the map
    unlisted = sums_text("c" * 64)
    with pytest.raises(pool_exam.ExamRefused, match="not_listed_in_its_sums"):
        attach(
            dataclasses.replace(
                registered,
                optimizer=dataclasses.replace(
                    registered.optimizer, coverage_plan_sums_sha256=sha(unlisted)
                ),
            ),
            document,
            unlisted,
            sets,
        )


def test_class_names_must_be_geometric_v1(monkeypatch):
    sets, document, sums, _plan, registered = _plan_and_sums()
    # the receipted rule (carbon.scoring.geometric_v1) refuses the fixture's names: they are not geometric-v1 names
    with pytest.raises(
        pool_exam.ExamRefused, match="coverage_plan_class_not_geometric_v1"
    ):
        pool_exam.attach_coverage_plan(registered, document, sums, sets)
    monkeypatch.setattr(pool_exam, "geometric_v1_names_valid", lambda classes: False)
    with pytest.raises(
        pool_exam.ExamRefused, match="coverage_plan_class_not_geometric_v1"
    ):
        pool_exam.attach_coverage_plan(registered, document, sums, sets)


def test_the_material_check_admits_a_plan_with_its_sums_and_refuses_a_partial_one():
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
    document = plan_document([BIG], {"t": BIG})
    good = {**material, "coverage_plan": document, "coverage_plan_sums": "x"}
    assert pool_version.check_material(good) is good
    for bad in [
        {**material, "coverage_plan": document},
        {**material, "coverage_plan_sums": "x"},
        {**material, "coverage_plan": document, "coverage_plan_sums": 1},
        {
            **material,
            "coverage_plan": plan_document([BIG], {"t": MID}),
            "coverage_plan_sums": "x",
        },
    ]:
        with pytest.raises(pool_exam.ExamRefused, match="pool_material_malformed"):
            pool_version.check_material(bad)


def _measure_kwargs(monkeypatch, material):
    """`PoolVariant.measure` up to `measure_pool` (recorded), with placeholder policies it must never read."""
    calls = []
    monkeypatch.setattr(pool_version, "registered_policies", lambda c, v: object())
    monkeypatch.setattr(pool_version, "registered_a_multiplier", lambda c, v: 3.0)
    monkeypatch.setattr(pool_version, "check_material", lambda m: m)
    monkeypatch.setattr(pool_grader, "load_pool", lambda document: document)
    monkeypatch.setattr(pool_version.pool_adapters, "official_binding", lambda *a: None)
    monkeypatch.setattr(
        pool_exam, "measure_pool", lambda **kwargs: calls.append(kwargs) or "graded"
    )
    adapter = SimpleNamespace(
        _challenge_id="f02",
        _kind="fixture",
        VERSION="9.9",
        _module=SimpleNamespace(measure=None),
        _without_pool=pool_version.PoolVariant._without_pool,
    )
    pool_version.PoolVariant.measure(
        adapter,
        bank_rows=[],
        outputs=[],
        repeats=[],
        definition={"pool": material},
        limits=None,
        objective=None,
        train_raw=None,
        names=None,
    )
    (call,) = calls
    return call


def test_the_adapter_hands_the_plan_material_to_the_exam_and_never_reads_the_policies(
    monkeypatch,
):
    base = {"sets": [[{}]], "input_dtype": "float32"}
    call = _measure_kwargs(monkeypatch, base)
    assert "coverage_plan" not in call and "coverage_plan_sums" not in call
    document = plan_document([BIG], {"t": BIG})
    call = _measure_kwargs(
        monkeypatch, {**base, "coverage_plan": document, "coverage_plan_sums": "x"}
    )
    assert call["coverage_plan"] == document and call["coverage_plan_sums"] == "x"


# --- the official exam path and its SE -------------------------------------------------------------------------------------


def _exam_sets():
    return (
        tuple(exam_target(f"big{i}", 20 + i) for i in range(4))
        + (exam_target("small0", 60),),
        tuple(exam_target(f"big{4 + i}", 40 + i) for i in range(4))
        + (exam_target("small1", 70),),
    )


def _exam_plan(the_sets):
    targets = {
        s.target_id: (SMALL if s.target_id.startswith("small") else BIG)
        for group in the_sets
        for s in group
    }
    document = plan_document([BIG, SMALL], targets)
    plan = coverage_plan(document)
    sums = sums_text(plan.sha256)
    return document, sums, plan


def _measure(the_sets, policies, serve, **plan_material):
    rows = exam_rows(the_sets)
    outputs = serve([r["inputs"] for r in rows])
    capture = {}
    result = pool_exam.measure_pool(
        binding=toy_binding(),
        sets=the_sets,
        policies=policies,
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        base_measure=fake_measure,
        base_arguments=ARGUMENTS,
        speed_call_seconds=FAST,
        ceiling_seconds=CEILING,
        capture=capture,
        **plan_material,
    )
    return result, capture["se_basis"]


def test_the_multi_class_exam_grades_aggregates_and_recomposes_like_the_grade(
    geometric_v1_stand_in,
):
    the_sets = _exam_sets()
    document, sums, plan = _exam_plan(the_sets)
    policies = dataclasses.replace(
        POLICIES,
        optimizer=dataclasses.replace(
            POLICIES.optimizer,
            d_aggregate="balanced_region_mean",
            a_gen_aggregate="balanced_region_mean",
            coverage_plan_sha256=plan.sha256,
            coverage_plan_sums_sha256=sha(sums),
        ),
    )
    result, basis = _measure(
        the_sets,
        policies,
        good_serve,
        coverage_plan=document,
        coverage_plan_sums=sums,
    )
    assert basis["gated"] is False
    assert basis["classes"] == [BIG, SMALL]
    assert basis["d_aggregate"] == basis["a_gen_aggregate"] == "balanced_region_mean"
    assert [[t["region"] for t in s] for s in basis["sets"]] == [
        [BIG] * 4 + [SMALL],
        [BIG] * 4 + [SMALL],
    ]
    recomposed = pool_exam.total_of_targets(basis, basis["sets"])
    assert recomposed == pytest.approx(0.5 * result["A"] + 0.5 * result["D"], abs=1e-12)
    assert basis["total"] == pytest.approx(recomposed, abs=1e-12)
    # the recomposition is the balanced one: by hand, per set, the mean of the class means
    by_hand = []
    for targets in basis["sets"]:
        big = [t for t in targets if t["region"] == BIG]
        small = [t for t in targets if t["region"] == SMALL]
        d = statistics.fmean(
            [
                statistics.fmean(t["d"] for t in big),
                statistics.fmean(t["d"] for t in small),
            ]
        )
        gen = statistics.fmean(
            [
                statistics.fmean(t["agen"] for t in big),
                statistics.fmean(t["agen"] for t in small),
            ]
        )
        a = pool_grader.combine_a(basis["a_bank"], gen, basis["a_rule"])
        by_hand.append((a, min(d, basis["c"])))
    total = 0.5 * statistics.fmean(a for a, _d in by_hand) + 0.5 * statistics.fmean(
        d for _a, d in by_hand
    )
    assert recomposed == pytest.approx(total, abs=1e-12)
    spread, sizes = pool_exam.target_bootstrap_se(basis, KEY)
    assert sizes == [5, 5] and spread >= 0.0


def test_a_registered_version_grades_and_captures_exactly_as_before():
    """No aggregate and no plan: the same grade and the same SE basis keys as the 3q head (no class, no order)."""
    the_sets = _exam_sets()
    result, basis = _measure(the_sets, POLICIES, good_serve)
    assert set(basis) == {"gated", "a_bank", "c", "a_rule", "sets", "total"}
    assert all(set(t) == {"d", "agen"} for s in basis["sets"] for t in s)
    again, _ = _measure(the_sets, POLICIES, good_serve)
    assert result == again


def test_the_exam_refuses_a_registered_plan_without_its_material():
    the_sets = _exam_sets()
    _document, sums, plan = _exam_plan(the_sets)
    policies = dataclasses.replace(
        POLICIES,
        optimizer=dataclasses.replace(
            POLICIES.optimizer,
            d_aggregate="balanced_region_mean",
            coverage_plan_sha256=plan.sha256,
            coverage_plan_sums_sha256=sha(sums),
        ),
    )
    with pytest.raises(pool_exam.ExamRefused, match="missing_from_the_sealed_pack"):
        _measure(the_sets, policies, good_serve)


def test_the_balanced_bootstrap_resamples_within_each_class():
    basis = {
        "gated": False,
        "a_bank": 0.7,
        "c": 1.0,
        "a_rule": {"kind": "mean"},
        "d_aggregate": "balanced_region_mean",
        "a_gen_aggregate": None,
        "classes": [BIG, SMALL],
        "sets": [
            [{"d": d, "agen": None, "region": BIG} for d in (0.2, 0.4, 0.6, 0.8)]
            + [{"d": 0.0, "agen": None, "region": SMALL}],
        ],
    }
    import numpy as np

    generator = np.random.Generator(np.random.PCG64(7))
    for _ in range(50):
        drawn = pool_exam._stratified_draw(
            generator, basis["sets"][0], basis["classes"]
        )
        assert [t["region"] for t in drawn] == [BIG] * 4 + [SMALL]
    # the single small target is in every resample, so D's small class mean is always 0.0
    assert pool_exam.total_of_targets(basis, basis["sets"]) == pytest.approx(
        0.5 * 0.7 + 0.5 * statistics.fmean([0.5, 0.0])
    )
    spread, sizes = pool_exam.target_bootstrap_se(basis, KEY)
    assert sizes == [5] and spread > 0.0


def test_a_plan_is_a_frozen_value():
    plan = three_class_plan(1)
    assert isinstance(plan, CoveragePlan)
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.classes = ()


def test_motor_1p8_menu_scores_3_of_4_tasks_per_epoch():
    """Owner, typed in mc-exam-B 10 Nov 21:4x: 'Motor has 4 tasks, 3 scored per epoch; the fewer-than-3 exception
    label is dropped.' Motor 1.8's menu registers tasks_per_epoch 3 and no min_tasks_exception; Cooling 1.8 scores
    every task (no tasks_per_epoch).
    """
    document = json.loads(pool_version.CONSTANTS.read_bytes())
    motor = document["versions"]["electric-motor-magnetics 1.8"]["menu"]
    assert motor["tasks_per_epoch"] == 3
    assert "min_tasks_exception" not in motor
    assert "tasks_per_epoch" not in document["versions"]["chip-cold-plate 1.8"]["menu"]

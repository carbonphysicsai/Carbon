"""Out-of-range A_gen on the pool path (OWNER-ACCURACY-OOD-MIN-01 items 1 and 4; Validator 4 Nov 21:22 gaps 1-3).

Claims, for the NEW ``a_gen_aggregate == "ood_class_mean"`` only (every registered version is unchanged):
1. A_gen is scored on out-of-range classes only: a reserved slice on an in-range target refuses, and so does a class
   that mixes in-range and out-of-range targets (min(A, A_gen) would compare in-range with a mix).
2. Out-of-range classes with fewer than N reserved cases pool into one ``other_ood`` class; N is the registered
   ``a_gen_min_class_cases`` (the version plan's), required with the mode and refused without it; never defaulted.
3. Per-class floors are REPORTED against the TRAIN-kernel (`agen_class_report`, custody, report only).
Plus: the registration reads N with no default, and the exam's SE basis recomposes the pooled A_gen exactly as graded.

Every class name, count and value is a SYNTHETIC fixture: none is a production class list, N, scale or floor.
"""

from __future__ import annotations

import dataclasses
import json
import statistics
from types import SimpleNamespace

import pytest
from test_pool_exam import POLICIES
from test_pool_multiclass_regions import (  # noqa: F401  (geometric_v1_stand_in is a fixture)
    _measure,
    geometric_v1_stand_in,
    plan_document,
    sha,
    sums_text,
)
from test_pool_plugin import SHELL, good_serve
from test_pool_plugin import toy_target as exam_target

from carbon.scoring import pool_exam, pool_grader, pool_version
from carbon.scoring.design_fidelity import benefit
from carbon.scoring.pool_grader import (
    OTHER_OOD,
    PoolRefused,
    agen_accuracy,
    agen_buckets,
    agen_class_report,
    coverage_plan,
)
from tests.cpu.test_pool_grader import HONESTY, OPTIMIZER

IN, EDGE, CORNER, STEP = "fixture:in", "fixture:edge", "fixture:corner", "fixture:step"
SCALES = {"f": 0.1}


def stand(target_id, extended, cases):
    """A stand-in target: ``cases`` reserved points of truth f = 0 (`agen_buckets` / A_gen read only these fields)."""
    return SimpleNamespace(
        target_id=target_id,
        extended=extended,
        agen=tuple(range(cases)),
        outputs=("f",),
        conditions={"case": target_id},
        designs=tuple((float(n),) for n in range(max(cases, 1))),
        truths=tuple({"f": 0.0} for _ in range(max(cases, 1))),
    )


def errors(by_target):
    """A model whose error on every reserved point of a target is that target's value."""

    def predict(conditions, designs):
        return [{"f": by_target[conditions["case"]]} for _ in designs]

    return predict


def atom(error):
    return benefit(error / SCALES["f"])


def the_set():
    """2 in-range targets (no slice), EDGE 2 x 4 cases, CORNER 1 x 2, STEP 1 x 1."""
    specs = [
        stand("i0", False, 0),
        stand("i1", False, 0),
        stand("e0", True, 4),
        stand("e1", True, 4),
        stand("c0", True, 2),
        stand("s0", True, 1),
    ]
    classes = {"i0": IN, "i1": IN, "e0": EDGE, "e1": EDGE, "c0": CORNER, "s0": STEP}
    return specs, coverage_plan(plan_document([IN, EDGE, CORNER, STEP], classes))


ERR = {"i0": 0.0, "i1": 0.0, "e0": 0.0, "e1": 0.1, "c0": 0.3, "s0": 0.9}


def policy(plan, n):
    return dataclasses.replace(
        OPTIMIZER,
        a_gen_aggregate="ood_class_mean",
        a_gen_min_class_cases=n,
        coverage_plan_sha256=plan.sha256,
        coverage_plan_sums_sha256=sha(sums_text(plan.sha256)),
        coverage_plan=plan,
    )


# ---------------------------------------------------------------- 2. small classes pool into other OOD


def test_classes_below_n_cases_pool_into_other_ood_and_each_bucket_is_its_own_mean():
    specs, plan = the_set()
    buckets, order = agen_buckets(specs, plan, 3)
    assert order == (EDGE, OTHER_OOD)
    assert buckets == (None, None, EDGE, EDGE, OTHER_OOD, OTHER_OOD)
    got = agen_accuracy(
        specs,
        errors(ERR),
        SCALES,
        aggregate="ood_class_mean",
        plan=plan,
        min_class_cases=3,
    )
    edge = statistics.fmean([atom(0.0), atom(0.1)])
    other = statistics.fmean(
        [atom(0.3), atom(0.9)]
    )  # per TARGET, as every A_gen mean here
    assert got == pytest.approx(statistics.fmean([edge, other]), abs=1e-15)
    assert got == pool_grader.agen_for(specs, errors(ERR), SCALES, policy(plan, 3))


def test_with_n_one_no_class_pools_and_with_a_large_n_every_class_pools():
    specs, plan = the_set()
    assert agen_buckets(specs, plan, 1)[1] == (EDGE, CORNER, STEP)
    assert agen_buckets(specs, plan, 100)[1] == (OTHER_OOD,)
    one = agen_accuracy(
        specs,
        errors(ERR),
        SCALES,
        aggregate="ood_class_mean",
        plan=plan,
        min_class_cases=1,
    )
    assert one == pytest.approx(
        statistics.fmean(
            [statistics.fmean([atom(0.0), atom(0.1)]), atom(0.3), atom(0.9)]
        ),
        abs=1e-15,
    )


# ---------------------------------------------------------------- 1. out of range only


def test_a_reserved_slice_on_an_in_range_target_refuses():
    specs, plan = the_set()
    specs[0] = stand("i0", False, 2)
    with pytest.raises(PoolRefused, match="a_gen_slice_on_an_in_range_target"):
        agen_buckets(specs, plan, 3)


def test_a_class_mixing_in_range_and_out_of_range_targets_refuses():
    specs, _plan = the_set()
    classes = {"i0": EDGE, "i1": IN, "e0": EDGE, "e1": EDGE, "c0": CORNER, "s0": STEP}
    plan = coverage_plan(plan_document([IN, EDGE, CORNER, STEP], classes))
    with pytest.raises(PoolRefused, match="mixes_in_range_and_out_of_range"):
        agen_buckets(specs, plan, 3)


def test_no_out_of_range_case_and_a_class_named_other_ood_refuse():
    specs = [stand("i0", False, 0), stand("e0", True, 0)]
    plan = coverage_plan(plan_document([IN, EDGE], {"i0": IN, "e0": EDGE}))
    with pytest.raises(PoolRefused, match="a_gen_has_no_out_of_range_case"):
        agen_buckets(specs, plan, 1)
    specs = [stand("e0", True, 2)]
    plan = coverage_plan(plan_document([OTHER_OOD], {"e0": OTHER_OOD}))
    with pytest.raises(PoolRefused, match="coverage_plan_class_named_other_ood"):
        agen_buckets(specs, plan, 1)


def test_n_goes_with_the_mode_only_and_is_a_positive_int():
    specs, plan = the_set()
    for n in (None, 0, -1, 2.0, True, "HUMAN_INPUT"):
        with pytest.raises(PoolRefused, match="a_gen_min_class_cases"):
            pool_grader._check_policies(policy(plan, n), HONESTY)
    for aggregate in (None, "balanced_region_mean"):
        bad = dataclasses.replace(
            policy(plan, 3), a_gen_aggregate=aggregate, a_gen_min_class_cases=3
        )
        with pytest.raises(PoolRefused, match="a_gen_min_class_cases"):
            pool_grader._check_policies(bad, HONESTY)
    pool_grader._check_policies(policy(plan, 3), HONESTY)
    with pytest.raises(PoolRefused, match="a_gen_min_class_cases"):
        agen_accuracy(specs, errors(ERR), SCALES, min_class_cases=3)


def test_the_plain_and_balanced_modes_are_unchanged():
    specs, plan = the_set()
    plain = agen_accuracy(specs, errors(ERR), SCALES)
    assert plain == pytest.approx(
        statistics.fmean(
            [
                statistics.fmean([atom(0.0)] * 4),
                statistics.fmean([atom(0.1)] * 4),
                atom(0.3),
                atom(0.9),
            ]
        ),
        abs=1e-15,
    )
    # balanced still demands a slice in EVERY plan class (the in-range class has none here)
    with pytest.raises(PoolRefused, match="a_gen_class_without_a_reserved_slice"):
        agen_accuracy(
            specs, errors(ERR), SCALES, aggregate="balanced_region_mean", plan=plan
        )


# ---------------------------------------------------------------- 3. floors reported against the TRAIN-kernel


def test_the_class_report_sets_each_bucket_against_the_train_kernel_and_grades_nothing():
    specs, plan = the_set()
    kernel = {**ERR, "e0": 0.2, "e1": 0.2, "c0": 0.2, "s0": 0.2}
    rows = agen_class_report(
        specs, errors(ERR), errors(kernel), SCALES, policy(plan, 3)
    )
    assert [(r["class"], r["members"], r["cases"]) for r in rows] == [
        (EDGE, [EDGE], 8),
        (OTHER_OOD, [CORNER, STEP], 3),
    ]
    edge = rows[0]
    assert edge["reference_a_gen"] == pytest.approx(atom(0.2), abs=1e-15)
    assert edge["gap"] == pytest.approx(
        edge["a_gen"] - edge["reference_a_gen"], abs=1e-15
    )
    json.dumps(rows)  # JSON-ready for the custody report
    with pytest.raises(PoolRefused, match="needs_ood_class_mean"):
        agen_class_report(specs, errors(ERR), errors(kernel), SCALES, OPTIMIZER)


# ---------------------------------------------------------------- the registration and the exam


def test_the_registration_reads_n_with_no_default():
    assert pool_version._min_class_cases(pool_version._ABSENT) is None
    for bad in (None, "HUMAN_INPUT", 0, -2, 2.0, True, "5"):
        with pytest.raises(pool_version.PoolConstantsNotRegistered):
            pool_version._min_class_cases(bad)
    assert pool_version._min_class_cases(5) == 5


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_exam_recomposes_the_pooled_out_of_range_a_gen_like_the_grade():
    the_sets = tuple(
        tuple(exam_target(f"e{s}{i}", 20 + 10 * s + i, shell=SHELL) for i in range(4))
        + (exam_target(f"c{s}", 60 + s, shell=SHELL),)
        for s in range(2)
    )
    classes = {t.target_id: (CORNER if t.target_id.startswith("c") else EDGE)
               for group in the_sets for t in group}  # fmt: skip
    document = plan_document([EDGE, CORNER], classes)
    plan = coverage_plan(document)
    sums = sums_text(plan.sha256)
    # the one CORNER target per set is below N (it pools); every EDGE class holds more
    n = max(len(group[4].agen) for group in the_sets) + 1
    assert all(sum(len(t.agen) for t in group[:4]) >= n for group in the_sets)
    policies = dataclasses.replace(
        POLICIES,
        optimizer=dataclasses.replace(
            POLICIES.optimizer,
            a_gen_aggregate="ood_class_mean",
            a_gen_min_class_cases=n,
            coverage_plan_sha256=plan.sha256,
            coverage_plan_sums_sha256=sha(sums),
        ),
    )
    result, basis = _measure(
        the_sets, policies, good_serve, coverage_plan=document, coverage_plan_sums=sums
    )
    assert basis["agen_orders"] == [[EDGE, OTHER_OOD], [EDGE, OTHER_OOD]]
    assert [[t["agen_region"] for t in s] for s in basis["sets"]] == [
        [EDGE] * 4 + [OTHER_OOD]
    ] * 2
    recomposed = pool_exam.total_of_targets(basis, basis["sets"])
    assert recomposed == pytest.approx(0.5 * result["A"] + 0.5 * result["D"], abs=1e-12)
    spread, sizes = pool_exam.target_bootstrap_se(basis, "sha256:" + "ab" * 32)
    assert sizes == [5, 5] and spread >= 0.0


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_broken_out_of_range_structure_is_the_exams_refusal_before_any_grade():
    specs, plan = the_set()
    specs[0] = stand("i0", False, 2)  # a slice on an in-range target
    document = plan_document(plan.classes, dict(plan.targets))
    sums = sums_text(plan.sha256)
    policies = dataclasses.replace(
        POLICIES,
        optimizer=dataclasses.replace(policy(plan, 3), coverage_plan=None),
    )
    with pytest.raises(
        pool_exam.ExamRefused, match="a_gen_slice_on_an_in_range_target"
    ):
        pool_exam.attach_coverage_plan(policies, document, sums, (tuple(specs),))
    specs[0] = stand("i0", False, 0)
    attached = pool_exam.attach_coverage_plan(policies, document, sums, (tuple(specs),))
    assert attached.optimizer.coverage_plan == plan

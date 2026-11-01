"""Balanced region scoring of the pool grader (new exam versions only; Q7 of WEEK1_EXAM_VALUE_ANSWERS).

Claims: with no ``d_aggregate`` a set's D is the plain mean of its targets' d (every registered version, bit for bit); with
``balanced_region_mean`` it is the mean over region classes (in_train, extended_shell) of each class's mean d, so a regime with
few targets cannot be averaged away; a set with one region class equals the plain mean; the per-region report is custody only;
the aggregation is validated and read from the registration without a default. Targets are stand-ins graded to chosen d.
"""

from __future__ import annotations

import dataclasses
import statistics
from types import SimpleNamespace

import pytest

from carbon.scoring import pool_grader, pool_version
from carbon.scoring.pool_grader import (
    OptimizerPolicy,
    PoolRefused,
    TargetGrade,
    grade_set,
)
from tests.cpu.test_pool_grader import HONESTY, OPTIMIZER, oracle, toy_target

BALANCED = dataclasses.replace(OPTIMIZER, d_aggregate="balanced_region_mean")


def stand_ins(monkeypatch, ds, extended):
    """Targets whose grade is the chosen d (the grader's own per-target arithmetic is not under test here)."""
    specs = [
        SimpleNamespace(target_id=f"t{i}", extended=flag)
        for i, flag in enumerate(extended)
    ]
    by_id = {s.target_id: d for s, d in zip(specs, ds, strict=True)}

    def grade(spec, predict, optimizer, honesty):
        d = by_id[spec.target_id]
        return TargetGrade(
            spec.target_id, "sha256:x", d, d, 1.0, 0.0, True, 0, 1, "graded", False
        )

    monkeypatch.setattr(pool_grader, "grade_target", grade)
    return specs


def test_without_an_aggregate_the_set_d_is_the_plain_mean_of_the_targets(monkeypatch):
    ds = [1.0, 1.0, 1.0, 1.0, 1.0, 0.0]
    specs = stand_ins(monkeypatch, ds, [False] * 5 + [True])
    result = grade_set(specs, None, OPTIMIZER, HONESTY)
    assert result.d == statistics.fmean(ds) and result.regions == ()


def test_a_bad_regime_cannot_hide_behind_a_good_majority(monkeypatch):
    # F08's case: five near-perfect targets in TRAIN and one total miss in the shell
    ds = [1.0, 1.0, 1.0, 1.0, 1.0, 0.0]
    specs = stand_ins(monkeypatch, ds, [False] * 5 + [True])
    plain = grade_set(specs, None, OPTIMIZER, HONESTY)
    balanced = grade_set(specs, None, BALANCED, HONESTY)
    assert plain.d == pytest.approx(5 / 6)
    assert balanced.d == pytest.approx(
        0.5
    )  # the mean of the in_train mean (1.0) and the extended_shell mean (0.0)
    assert dict(balanced.regions) == {"in_train": 1.0, "extended_shell": 0.0}
    assert [name for name, _ in balanced.regions] == list(pool_grader.REGION_CLASSES)


def test_each_region_is_its_own_mean_and_a_single_region_equals_the_plain_mean(
    monkeypatch,
):
    ds = [0.9, 0.7, 0.5, 0.3, 0.1]
    specs = stand_ins(monkeypatch, ds, [False, False, True, True, True])
    result = grade_set(specs, None, BALANCED, HONESTY)
    assert dict(result.regions) == pytest.approx(
        {"in_train": 0.8, "extended_shell": 0.3}
    )
    assert result.d == pytest.approx((0.8 + 0.3) / 2)
    only_train = stand_ins(monkeypatch, ds, [False] * 5)
    same = grade_set(only_train, None, BALANCED, HONESTY)
    assert same.d == pytest.approx(statistics.fmean(ds)) and [
        n for n, _ in same.regions
    ] == ["in_train"]
    only_shell = stand_ins(monkeypatch, ds, [True] * 5)
    assert grade_set(only_shell, None, BALANCED, HONESTY).d == pytest.approx(
        statistics.fmean(ds)
    )


def test_the_public_view_of_a_set_shows_no_region(monkeypatch):
    specs = stand_ins(monkeypatch, [1.0, 0.0], [False, True])
    public = grade_set(specs, None, BALANCED, HONESTY).public()
    assert set(public) == {"d", "reasons"} and "region" not in str(public)


def test_a_real_target_is_in_train_and_the_region_class_follows_its_kind():
    spec = toy_target("real", seed=2)
    assert pool_grader.region_class(spec) == "in_train"
    assert pool_grader.region_class(SimpleNamespace(extended=True)) == "extended_shell"
    # real targets: balanced over one region class is the plain mean, bit for bit
    specs = [toy_target(f"t{i}", seed=i) for i in range(3)]
    predict = oracle(specs)
    assert (
        grade_set(specs, predict, BALANCED, HONESTY).d
        == grade_set(specs, predict, OPTIMIZER, HONESTY).d
    )


@pytest.mark.parametrize(
    "value", ["mean", "balanced", 1, True, ["balanced_region_mean"]]
)
def test_an_unknown_aggregate_is_refused(value):
    bad = dataclasses.replace(OPTIMIZER, d_aggregate=value)
    with pytest.raises(PoolRefused, match="d_aggregate"):
        grade_set([toy_target()], oracle([toy_target()]), bad, HONESTY)


def test_registered_versions_keep_the_plain_mean_and_the_aggregate_is_never_defaulted():
    import json

    assert OptimizerPolicy(budget=5, sigma0=0.3, population=None).d_aggregate is None
    assert pool_version._d_aggregate(None) is None
    assert pool_version._d_aggregate("balanced_region_mean") == "balanced_region_mean"
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version._d_aggregate(pool_version.HUMAN_INPUT)
    document = json.loads(pool_version.CONSTANTS.read_bytes())
    for name, entry in document["versions"].items():
        challenge, version = name.rsplit(" ", 1)
        try:
            policies = pool_version.registered_policies(challenge, version)
        except pool_version.PoolConstantsNotRegistered:
            continue
        assert policies.optimizer.d_aggregate is None, name
        assert "d_aggregate" not in entry["optimizer"], name


def test_the_grid_spec_carries_the_aggregate_without_changing_old_files():
    from carbon.scoring import pool_proof_grid as grid

    fields = {f.name: f for f in dataclasses.fields(grid.GridSpec)}
    assert fields["d_aggregate"].default is None

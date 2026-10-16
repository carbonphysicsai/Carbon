"""Prospective context and unchanged decision algebra on synthetic inputs only."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from carbon.design_search import indexed, tasks
from scripts.dev.score_lab import guarded419_context as context
from scripts.dev.score_lab import owner_v3 as owner
from scripts.dev.score_lab import owner_v3_n1 as n1
from tests.cpu.test_score_lab_owner_v3 import fixture


def load():
    return context.load(expected_sha256=context.REGISTRATION_SHA256)


def guarded_fixture(**kwargs):
    # Reissue ONLY artificial task identities to test equal decision algebra.
    # No historical physical labels/model/commitments are promoted.
    old, _, refs, intervals = fixture(**kwargs)
    rows = []
    for row in old["indices"]:
        sub = row["task"]
        identity = dict(
            sub["identity"],
            contract_version=context.JOB,
            observer_version=context.EVAL_OBSERVER,
        )
        task = tasks.task(
            "new-context-toy-" + sub["task_id"],
            identity=identity,
            conditions=sub["conditions"],
            strata=sub["strata"],
            candidates=sub["candidates"],
            actions=sub["actions"],
            objective=sub["objective"],
            limits=sub["limits"],
        )
        rows.append({**row, "task": task})
    task = indexed.indexed_task(
        "new-context-toy",
        index_axis="ambient_c",
        indices=rows,
        query_budget=10,
        value_equivalence=old["identity"]["value_equivalence"],
    )
    return old, task, refs, intervals


def test_new_registration_preserves_every_original_scoring_constant():
    reg = context.validate(load())
    parent = n1.registration(expected_sha256=n1.REGISTRATION_SHA256)
    context._check_registration(reg, parent)
    assert reg["scales"] == parent["scales"]
    assert reg["normalization_source"]["train_sha256"] == parent["train_sha256"]
    assert (
        reg["normalization_source"]["scale_receipt_sha256"]
        == parent["train_scale_receipt_sha256"]
    )
    assert "train_sha256" not in reg and "train_scale_receipt_sha256" not in reg
    assert reg["training_normalization"] == "NEW_ACCEPTED_CONSTRUCTION_ONLY"
    assert reg["historical_models_compatible"] is False
    assert (
        hashlib.sha256(
            (
                context.DIRECTORY.parent / "n1-diagnostic-v1/registration.json"
            ).read_bytes()
        ).hexdigest()
        == n1.REGISTRATION_SHA256
    )


@pytest.mark.parametrize(
    "defect",
    [
        "scale",
        "epsilon",
        "unit",
        "floor",
        "band",
        "normalization",
        "old_train_role",
        "new_wrapper",
    ],
)
def test_recomputed_or_reweighted_constants_and_roles_are_refused(defect):
    reg = context.validate(load())
    parent = n1.registration(expected_sha256=n1.REGISTRATION_SHA256)
    if defect == "scale":
        reg["scales"]["minutes"]["population_sd"] += 1
    elif defect in ("epsilon", "unit", "floor"):
        reg["scales"]["v_max_v"][defect] = {
            "epsilon": 0.1,
            "unit": "mV",
            "floor": 0.01,
        }[defect]
    elif defect == "band":
        reg["near_band"] = 0.2
    elif defect == "normalization":
        reg["training_normalization"] = "CAL_OR_EVAL"
    elif defect == "old_train_role":
        reg["normalization_source"]["role"] = "NEW_TRAIN"
    else:
        reg["new_wrapper"] = "CVAR"
    with pytest.raises(tasks.TaskError, match="exact approved"):
        context._check_registration(reg, parent)


def test_context_cannot_be_constructed_from_raw_registration_or_changed():
    reg = json.loads((context.DIRECTORY / "registration.json").read_bytes())
    with pytest.raises(tasks.TaskError, match="use guarded419_context.load"):
        context.Context(raw=json.dumps(reg).encode())
    with pytest.raises(tasks.TaskError, match="nominal"):
        context.validate(reg)
    with pytest.raises(tasks.TaskError, match="digest"):
        context.load(expected_sha256=n1.REGISTRATION_SHA256)
    value = load()
    with pytest.raises(AttributeError):
        value._raw = b"changed"
    reg["near_band"] = 99
    assert context.validate(value)["near_band"] == 0.1


def test_reciprocal_old_new_tasks_are_refused_without_context_fallback():
    old, new, _, _ = guarded_fixture()
    owner._validate(old)
    owner._validate(new, context=load())
    with pytest.raises(tasks.TaskError):
        owner._validate(new)
    with pytest.raises(tasks.TaskError):
        owner._validate(old, context=load())
    with pytest.raises(tasks.TaskError, match="nominal"):
        owner._validate(new, context={"job": context.JOB})


@pytest.mark.parametrize("bad", [None, 5, 40])
def test_context_mask_keeps_all_mandatory_bands_and_same_reference_decision(bad):
    old, new, refs, intervals = guarded_fixture(
        bad=bad, weights=[0, 0.1, 0.5, 0.3, 0.1]
    )
    before = owner.reference_mask(old, refs, intervals)
    after = owner.reference_mask(new, refs, intervals, context=load())
    for key in (
        "included",
        "reference_state",
        "reasons",
        "per_index",
        "reference_digest",
        "enclosure_digest",
    ):
        assert after[key] == before[key]
    assert after["projection"] == context.PROJECTION
    assert before["projection"] == owner.PROJECTION
    assert after["task_digest"] != before["task_digest"]
    original = copy.deepcopy(old)
    owner.reference_mask(new, refs, intervals, context=load())
    assert old == original


def test_raw_buyer_voltage_margin_stays_42_not_controller_target():
    sub = {"limits": [{"quantity": "v_max_v", "op": "<=", "value": 4.2}]}
    point = n1._point({"minutes": 20, "v_max_v": 4.195}, sub)
    assert point["margins"]["v_max_v"] == pytest.approx(0.005)


def test_new_judge_reuses_deadzone_algebra_and_requires_new_commitment():
    old, new, refs, intervals = guarded_fixture(weights=[0, 0.1, 0.5, 0.3, 0.1])

    def commit(task):
        return tasks.run_indexed_optimizer(
            task,
            lambda _band, action, _cond: {
                "minutes": 1 if action["choice"] == "a" else 2,
                "toy-margin": 1,
            },
            model_id="synthetic-context-parity",
        )["commitment"]

    original = owner.judge(old, commit(old), refs, intervals, scope="SYNTHETIC_FIXTURE")
    result = owner.judge(
        new, commit(new), refs, intervals, scope="SYNTHETIC_FIXTURE", context=load()
    )
    for key in (
        "kind",
        "regret_min",
        "regret_ranking_eligible",
        "historical_aggregate_regret_unchanged",
    ):
        assert result[key] == original[key]
    for actual, previous in zip(
        result["per_index"], original["per_index"], strict=True
    ):
        assert actual["weighted_regret_min"] == previous["weighted_regret_min"]
        assert actual["selected_objective"] == previous["selected_objective"]
        assert (
            actual["reference_best_objective"] == previous["reference_best_objective"]
        )
        assert actual["outcome"]["regret"] == previous["outcome"]["regret"]
        assert actual["outcome"]["task_digest"] != previous["outcome"]["task_digest"]
    assert result["job"] == context.JOB and original["job"] == owner.JOB
    assert result["schema"] == context.PROJECTION
    with pytest.raises(tasks.TaskError, match="commitment"):
        owner.judge(
            new, commit(old), refs, intervals, scope="SYNTHETIC_FIXTURE", context=load()
        )


def test_new_context_never_falls_back_to_old_producer():
    _, new, refs, intervals = guarded_fixture()
    with pytest.raises(tasks.TaskError, match="guarded419 EVAL producer"):
        owner.judge(
            new,
            {},
            refs,
            intervals,
            scope="SYNTHETIC_FIXTURE",
            context=load(),
            producer_evidence={"status": "PASS"},
        )


def test_new_n1_registration_selects_only_the_exact_committed_digest():
    assert n1.registration(
        expected_sha256=context.REGISTRATION_SHA256
    ) == context.validate(load())
    with pytest.raises(tasks.TaskError, match="registration digest"):
        n1.registration(expected_sha256="guarded419")


def test_legacy_evidence_cannot_be_scored_under_new_registration():
    from tests.cpu.test_score_lab_owner_v3_n1 import bindings, predictions, row

    old = row()
    with pytest.raises(tasks.TaskError):
        n1.score_leg(
            [old],
            predictions([old]),
            producer_bindings=bindings([old]),
            expected_registration_digest=context.REGISTRATION_SHA256,
            scope="SYNTHETIC_FIXTURE",
        )

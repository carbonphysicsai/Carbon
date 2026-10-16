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


def test_new_context_never_falls_back_to_old_producer(monkeypatch):
    from scripts.dev.score_lab import owner_v3_panel_export

    def forbidden(*args, **kwargs):
        raise AssertionError("old producer called for guarded context")

    monkeypatch.setattr(owner_v3_panel_export, "validate_for", forbidden)
    _, new, refs, intervals = guarded_fixture()
    with pytest.raises(tasks.TaskError):
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


def test_new_population_preserves_frozen_physical_inputs_law_and_roles():
    value = load()
    plan = context.acquisition_plan(value)
    parent = {**plan, "job": owner.JOB}
    original_jobs = owner.acquisition_inputs(
        parent, expected_digest=tasks.digest(parent), stage="evaluation"
    )["jobs"]
    new_jobs = owner.acquisition_inputs(
        plan, expected_digest=tasks.digest(plan), stage="evaluation", context=value
    )["jobs"]
    assert len(new_jobs) == len(original_jobs) == 120
    assert [{k: v for k, v in job.items() if k != "case_id"} for job in new_jobs] == [
        {k: v for k, v in job.items() if k != "case_id"} for job in original_jobs
    ]
    assert {job["case_id"] for job in new_jobs}.isdisjoint(
        job["case_id"] for job in original_jobs
    )
    old = owner.population_tasks(
        parent, expected_plan_digest=tasks.digest(parent), count=64
    )
    new = owner.population_tasks(
        plan, expected_plan_digest=tasks.digest(plan), count=64, context=value
    )
    assert len(new) == 64
    assert sum(row["role"] == "LEG" for row in new) == 32
    assert sum(row["role"] == "VALUE" for row in new) == 32
    for before, after in zip(old, new, strict=True):
        assert (
            before["role"] == after["role"]
            and before["population"] == after["population"] == "P"
        )
        assert before["outer_weight"] == after["outer_weight"] == 1
        assert before["task"]["task_digest"] != after["task"]["task_digest"]
        assert before["bank_cluster"] != after["bank_cluster"] == tasks.digest(plan)
        owner._validate(after["task"], context=value)
        for old_band, new_band in zip(
            before["task"]["indices"], after["task"]["indices"], strict=True
        ):
            assert old_band["buyer_weight"] == new_band["buyer_weight"]
            assert old_band["task"]["actions"] == new_band["task"]["actions"]
            assert old_band["task"]["limits"] == new_band["task"]["limits"]
            assert old_band["task"]["objective"] == new_band["task"]["objective"]
    assert new == owner.population_tasks(
        plan, expected_plan_digest=tasks.digest(plan), count=64, context=value
    )


def test_new_input_plan_refuses_changes_to_any_prospective_number():
    value = load()
    plan = context.acquisition_plan(value)
    plan["questions"]["seed"] += 1
    with pytest.raises(tasks.TaskError, match="frozen guarded"):
        owner.population_tasks(
            plan, expected_plan_digest=tasks.digest(plan), count=64, context=value
        )


def test_cli_context_schema_and_old_tasks_refuse_before_reference_files():
    from scripts.dev.score_lab import n1_diagnostic as cli
    from tests.cpu.test_score_lab_n1_diagnostic_cli import bundle

    manifest, artifacts, _ = bundle()
    manifest.update(job=context.JOB, registration_sha256=context.REGISTRATION_SHA256)

    class NoRead(dict):
        def __getitem__(self, key):
            raise AssertionError("material read before context refusal")

    with pytest.raises(cli.Refused, match="RUN_SCHEMA_CONTEXT_DIFFERS"):
        cli.evaluate(manifest, NoRead())
    manifest["schema"] = cli.GUARDED_SCHEMA

    class DrawsOnly(dict):
        def __getitem__(self, key):
            assert (
                key == manifest["draws"]
            ), "reference read before task context refusal"
            return artifacts[key]

    with pytest.raises(tasks.TaskError):
        cli.evaluate(manifest, DrawsOnly())


def unsealed_saved_members():
    """Artificial byte-join fixture, NOT nominal TRAIN/CAL/EVAL admission.

    Three saved-model shapes and two toy decisions exercise the private join.
    The real producer separately requires its exact eighteen-member/64-draw
    roster and actual CAL evidence; this fixture never calls that seal.
    """
    from scripts.dev.score_lab import n1_diagnostic as cli
    from tests.cpu.test_score_lab_n1_diagnostic_cli import _bytes, bundle

    manifest, artifacts, _ = bundle()
    draws = json.loads(artifacts[manifest["draws"]])
    for n, draw in enumerate(draws):
        rows = []
        for row in draw["task"]["indices"]:
            old = row["task"]
            sub = tasks.task(
                f"toy-new-{n}-{row['index_value']}",
                identity=dict(
                    old["identity"],
                    contract_version=context.JOB,
                    observer_version=context.EVAL_OBSERVER,
                ),
                conditions=old["conditions"],
                strata=old["strata"],
                candidates=old["candidates"],
                actions=old["actions"],
                objective=old["objective"],
                limits=old["limits"],
            )
            rows.append({**row, "task": sub})
        draw["task"] = indexed.indexed_task(
            f"toy-new-{n}",
            index_axis="ambient_c",
            indices=rows,
            query_budget=draw["task"]["identity"]["query_budget"],
            value_equivalence=draw["task"]["identity"]["value_equivalence"],
        )
    view_digest = "sha256:" + "9" * 64
    construction = {
        "schema": "carbon.scorelab.guarded419.role-separated-train128.v1",
        "scope": "SYNTHETIC_FIXTURE",
        "fixture": True,
        "binding_digest": "sha256:" + "1" * 64,
        "construction_jsonl_digest": "sha256:" + "2" * 64,
        "construction_offered": 105,
        "validation_offered": 23,
        "construction_accepted": 105,
        "validation_rows_used_for_fitting": 0,
        "historical_labels_or_models_reused": 0,
        "numerical_evaluation_reference": False,
        "qualification": False,
    }
    construction["receipt_digest"] = tasks.digest(construction)
    artifacts["construction.json"] = _bytes(construction)
    pinned = []
    for spec, recipe in zip(
        manifest["members"], ("default", "small", "wide"), strict=True
    ):
        spec.update(
            id=f"battery-v3-scorelab-guard419-stage128-dev-v1:{recipe}:seed11",
            recipe=recipe,
            seed=11,
            construction_receipt="construction.json",
            train_sha256="2" * 64,
            kit="carbon.battery-v3.guard419.stage128.kit.v1:"
            + construction["binding_digest"],
        )
        fit, prediction, commit_receipt = (
            json.loads(artifacts[spec[k]])
            for k in ("fit_receipt", "predictions", "commitment_receipt")
        )
        fit.update(
            model_id=spec["id"],
            kit=spec["kit"],
            export_digest=view_digest,
            recipe={"seed": 11},
        )
        fit["train"].update(
            sha256="sha256:" + spec["train_sha256"], records=105, excluded_non_finite=0
        )
        fit["code"]["recipe_id"] = recipe
        artifacts[spec["fit_receipt"]] = _bytes(fit)
        prediction.update(
            model_id=spec["id"],
            export_digest=view_digest,
            source_receipt_digest="sha256:"
            + hashlib.sha256(cli.carbon_arm.canonical(fit)).hexdigest(),
        )
        artifacts[spec["predictions"]] = _bytes(prediction)
        table = {
            (row["band"], row["candidate"], row["condition"]): row["values"]
            for row in prediction["rows"]
        }
        committed = []
        for i, draw in enumerate(draws):
            actions = {
                r["index_value"]: {
                    tasks.digest(action): candidate
                    for candidate, action in r["task"]["actions"].items()
                }
                for r in draw["task"]["indices"]
            }
            choice = tasks.run_indexed_optimizer(
                draw["task"],
                lambda band, action, condition, table=table, actions=actions: table[
                    (band, actions[band][tasks.digest(action)], condition["id"])
                ],
                model_id=spec["id"],
            )["commitment"]
            committed.append(
                {
                    "population_index": i,
                    **{
                        k: draw[k]
                        for k in ("population", "role", "outer_weight", "bank_cluster")
                    },
                    "commitment": choice,
                }
            )
        artifacts[spec["commitments"]] = b"".join(_bytes(row) for row in committed)
        commit_receipt.update(
            model_id=spec["id"],
            commitments_sha256=hashlib.sha256(
                artifacts[spec["commitments"]]
            ).hexdigest(),
            model_predictions_sha256=hashlib.sha256(
                artifacts[spec["predictions"]]
            ).hexdigest(),
        )
        artifacts[spec["commitment_receipt"]] = _bytes(commit_receipt)
        pinned.append(
            {
                **{
                    k: spec[k]
                    for k in (
                        "id",
                        "recipe",
                        "seed",
                        "kit",
                        "fit_source",
                        "train_sha256",
                    )
                },
                "construction_receipt_digest": construction["receipt_digest"],
                **{
                    hash_key: hashlib.sha256(artifacts[spec[file_key]]).hexdigest()
                    for file_key, hash_key in (
                        ("fit_receipt", "fit_receipt_sha256"),
                        ("predictions", "predictions_sha256"),
                        ("commitments", "commitments_sha256"),
                        ("commitment_receipt", "commitment_receipt_sha256"),
                    )
                },
            }
        )
    return manifest["members"], {"members": pinned}, artifacts, draws, view_digest


def test_unsealed_member_byte_join_retains_fresh_choices_and_train_identity():
    from scripts.dev.score_lab import n1_diagnostic as cli

    members, pretruth, files, draws, view = unsealed_saved_members()
    result = cli._guarded_cohort(
        members, pretruth, files.__getitem__, draws, view, "SYNTHETIC_FIXTURE"
    )
    assert set(result) == {member["id"] for member in members}
    for member in members:
        physical, choices = result[member["id"]]
        assert len(physical) == 60 and len(choices) == 2
        assert all(row["model_id"] == member["id"] for row in choices.values())


@pytest.mark.parametrize(
    "defect", ["seed", "binding", "validation_fit", "prediction_bytes"]
)
def test_unsealed_member_join_rejects_semantic_drift_even_with_updated_hashes(defect):
    from scripts.dev.score_lab import n1_diagnostic as cli
    from tests.cpu.test_score_lab_n1_diagnostic_cli import _bytes

    members, pretruth, files, draws, view = unsealed_saved_members()
    first, expected = members[0], pretruth["members"][0]
    if defect == "seed":
        fit = json.loads(files[first["fit_receipt"]])
        fit["recipe"]["seed"] = 29
        files[first["fit_receipt"]] = _bytes(fit)
        expected["fit_receipt_sha256"] = hashlib.sha256(
            files[first["fit_receipt"]]
        ).hexdigest()
    elif defect in ("binding", "validation_fit"):
        receipt = json.loads(files["construction.json"])
        receipt.pop("receipt_digest")
        receipt[
            (
                "binding_digest"
                if defect == "binding"
                else "validation_rows_used_for_fitting"
            )
        ] = ("sha256:" + "3" * 64 if defect == "binding" else 1)
        receipt["receipt_digest"] = tasks.digest(receipt)
        files["construction.json"] = _bytes(receipt)
        for row in pretruth["members"]:
            row["construction_receipt_digest"] = receipt["receipt_digest"]
    else:
        files[first["predictions"]] += b" "
    with pytest.raises(cli.Refused):
        cli._guarded_cohort(
            members, pretruth, files.__getitem__, draws, view, "SYNTHETIC_FIXTURE"
        )

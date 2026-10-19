"""Prospective synthetic graph adapter, below normal direct task admission."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from test_direct_v3_durable_tasks import _fixture

from carbon import research
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v4
from carbon.development_session import (
    bundle_graph_state,
    direct_graph_construction_worker,
    research_tasks,
    synthetic_graph_adapter,
)
from carbon.development_session.bundle_construction_worker import (
    INFER_PROGRAM,
    _digest,
    _stage_bundle_modules,
    _stage_modules,
    _tensors,
)
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.development_session.profile import canonical
from carbon.development_session.research_ledger import VERSION
from carbon.development_session.research_workspace import ResearchWorkspace
from carbon.level4 import graph, initializers, intake, staging, submission
from carbon.level4.allowlist import Allowlist
from carbon.level4.tooling import through_bprime


def _graph_case():
    import jax.numpy as jnp

    material = bundle_material_v4()
    allowed = Allowlist(material["allowlist_bytes"])
    interface = synthetic_graph_adapter.graph_interface()
    _, forward, _ = through_bprime(
        lambda scale, forcing: scale * forcing,
        (
            jnp.zeros((1,), jnp.float32),
            jnp.ones((4, 8, 8, 1), jnp.float32),
        ),
        role="forward",
        allowlist=allowed,
        input_names=["params/0", "inputs/forcing"],
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    init_spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(forward),
        "parameters": [
            {
                "input": "params/0",
                "initializer": "zeros",
                "fan_in_axes": [],
                "fan_out_axes": [],
            }
        ],
    }
    manifest, files = submission.build(
        challenge=material["construction_kit"]["id"],
        interface=interface.digest(),
        allowlist=allowed,
        forward=forward,
        init_spec=init_spec,
    )
    kit = material["construction_kit"]
    recipe = ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": {
                "id": kit["id"],
                "version": "development-graph-adapter-test",
                "train_digest": kit["train_digest"],
                "interface_digest": kit["interface_digest"],
                "construction_limits_digest": kit["construction_limits_digest"],
            },
            "source": {
                "kind": "graph",
                "submission_digest": submission.digest(manifest),
            },
            "procedure": {
                "entrypoint": None,
                "configuration": {
                    "training": {
                        "optimizer": "sgd",
                        "steps": 4,
                        "learning_rate": 0.5,
                    }
                },
                "train_use": {
                    "dataset": synthetic_graph_adapter.TRAIN_USE,
                    "coverage": "all",
                },
                "initial_state": None,
            },
            "output": {
                "format": synthetic_graph_adapter.OUTPUT_FORMAT,
                "interface_digest": kit["interface_digest"],
            },
        }
    )
    return material, allowed, recipe, submission.canonical(manifest), files


def test_direct_graph_task_retains_exact_admitted_source_after_workspace_changes(
    tmp_path, monkeypatch
):
    material, _allowed, recipe, raw_manifest, files = _graph_case()
    request, provider, discovery = _fixture(tmp_path, monkeypatch, material)
    # Isolate source custody on the old test kit. Production discovery only
    # selects the prospectively registered graph adapter on kit 1.3.
    monkeypatch.setattr(
        discovery,
        "graph_adapter_for",
        lambda key: (
            synthetic_graph_adapter.ADAPTER_ID
            if key == material["challenge_key"]
            else None
        ),
        raising=False,
    )
    graph_recipe = recipe.to_dict()
    graph_recipe["challenge"]["version"] = material["construction_kit"]["version"]
    request = replace(request, recipe=graph_recipe)
    tasks = provider()
    workspace = ResearchWorkspace(tasks.ledger, "miner")
    workspace.put(staging.WORKSPACE_MANIFEST, raw_manifest)
    for name, body in files.items():
        workspace.put(staging.WORKSPACE_PREFIX + name[7:] + ".json", body)
    expected = canonical(staging.envelope(raw_manifest, files))
    started = tasks.start_research_task(request)
    cancelled_request = replace(request, idempotency_key="direct-graph-cancel-002")
    cancelled_task = tasks.start_research_task(cancelled_request).task.task_id
    task_id = started.task.task_id
    assert started.created
    assert (
        tasks._source_envelope(
            task_id.value, ConstructionRecipe.from_dict(graph_recipe)
        )
        == expected
    )
    tasks.close()

    workspace.put(
        staging.WORKSPACE_MANIFEST,
        b"{}",
        expected_digest=workspace.current_digest(staging.WORKSPACE_MANIFEST),
    )
    reopened = provider()
    try:
        assert not reopened.start_research_task(request).created
        assert (
            reopened._source_envelope(
                task_id.value, ConstructionRecipe.from_dict(graph_recipe)
            )
            == expected
        )
        children = reopened._children(task_id)
        cancelled_children = reopened._children(cancelled_task)
        monkeypatch.setattr(
            reopened.ledger,
            "operation_state",
            lambda identity, *, owner: (
                "SUCCEEDED"
                if identity in (children[0], cancelled_children[0])
                else None
            ),
        )

        def refused(*args, **kwargs):
            assert kwargs["source_envelope"] == expected
            raise direct_graph_construction_worker.GraphConstructionDecision(
                "REFUSED", "graph_submission_invalid", "graph_shape_invalid"
            )

        monkeypatch.setattr(
            direct_graph_construction_worker,
            "reconstruct_and_infer_graph_public",
            refused,
        )
        terminal = reopened.run_queued_task(task_id)
        assert terminal.state is research.DirectTaskStateV3.REFUSED
        assert terminal.terminal_receipt.refusal_code == "graph_submission_invalid"
        assert reopened.private_attempt(task_id) is None

        def cancel_then_refuse(*args, **kwargs):
            assert kwargs["source_envelope"] == expected
            reopened.cancel_research_task(
                research.DirectCancelTaskRequestV3(
                    request.challenge_key, cancelled_task, "cancel-graph-build-002"
                )
            )
            raise direct_graph_construction_worker.GraphConstructionDecision(
                "REFUSED", "graph_submission_invalid", "graph_shape_invalid"
            )

        monkeypatch.setattr(
            research_tasks, "request_cancel", lambda *args, **kwargs: None
        )
        monkeypatch.setattr(
            direct_graph_construction_worker,
            "reconstruct_and_infer_graph_public",
            cancel_then_refuse,
        )
        cancelled = reopened.run_queued_task(cancelled_task)
        assert cancelled.state is research.DirectTaskStateV3.CANCELLED
        assert cancelled.terminal_receipt.refusal_code is None
        assert reopened.private_attempt(cancelled_task) is None
    finally:
        reopened.close()

    import sqlite3

    with sqlite3.connect(tmp_path / "tasks" / "direct-tasks.sqlite3") as db:
        db.execute(
            "UPDATE direct_task_sources SET body=? WHERE id=?", (b"{}", task_id.value)
        )
    with pytest.raises(ValueError, match="retained direct graph source differs"):
        provider()
    with sqlite3.connect(tmp_path / "tasks" / "direct-tasks.sqlite3") as db:
        db.execute(
            "UPDATE direct_task_sources SET body=? WHERE id=?", (b"", task_id.value)
        )
    source_path = tasks._source_path(task_id.value)
    source_path.write_bytes(b"{}")
    with pytest.raises(ValueError, match="retained direct graph source differs"):
        provider()


@pytest.mark.parametrize("inside_ledger_root", [False, True])
def test_direct_graph_source_bytes_count_against_finite_retention_budget(
    tmp_path, monkeypatch, inside_ledger_root
):
    material, _allowed, recipe, raw_manifest, files = _graph_case()
    task_root = (
        tmp_path / "ledger" / "tasks" if inside_ledger_root else tmp_path / "tasks"
    )
    request, provider, discovery = _fixture(
        tmp_path, monkeypatch, material, task_root=task_root
    )
    monkeypatch.setattr(
        discovery,
        "graph_adapter_for",
        lambda key: (
            synthetic_graph_adapter.ADAPTER_ID
            if key == material["challenge_key"]
            else None
        ),
        raising=False,
    )
    graph_recipe = recipe.to_dict()
    graph_recipe["challenge"]["version"] = material["construction_kit"]["version"]
    request = replace(request, recipe=graph_recipe)
    tasks = provider()
    ledger = tasks.ledger
    workspace = ResearchWorkspace(ledger, "miner")
    workspace.put(staging.WORKSPACE_MANIFEST, raw_manifest)
    for name, body in files.items():
        workspace.put(staging.WORKSPACE_PREFIX + name[7:] + ".json", body)
    envelope = canonical(staging.envelope(raw_manifest, files))
    baseline = ledger.check_storage()
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": {
                "retained_bytes": baseline + 1024**2 + 4 * len(envelope) + 65536 + 8192
            },
            "elapsed_seconds": None,
            "campaign_id": "direct-graph-source-retention-test",
            "implementation": "fixture",
            "objective": "fixture",
            "sampling": "fixture",
            "control": "none",
            "selection": "none",
            "replica_policy": "fixture",
            "provider": "none",
            "owner": "miner",
        }
    )
    accepted = []
    try:
        for index in range(32):
            candidate = replace(request, idempotency_key=f"graph-retention-{index:03d}")
            try:
                task = tasks.start_research_task(candidate).task
            except research.ResearchTaskProviderError as error:
                assert error.code is research.ResearchServiceErrorCode.BOUND_EXCEEDED
                break
            accepted.append(task)
            if index == 0:
                used = ledger.check_storage()
                assert not tasks.start_research_task(candidate).created
                assert ledger.check_storage() == used
        else:
            pytest.fail("finite retained_bytes cap did not refuse repeated graph tasks")
        assert accepted
        retained = list((ledger.root / "direct-task-sources").glob("*.json"))
        assert len(retained) == len(accepted)
        assert all(path.read_bytes() == envelope for path in retained)
        import sqlite3

        with sqlite3.connect(task_root / "direct-tasks.sqlite3") as db:
            assert db.execute(
                "SELECT COUNT(*),MAX(LENGTH(body)) FROM direct_task_sources"
            ).fetchone() == (len(accepted), 0)
    finally:
        tasks.close()


@pytest.mark.skipif(os.name == "nt", reason="G3 parser needs POSIX rlimits")
@pytest.mark.parametrize("optimizer", ["sgd", "adam"])
def test_real_submitted_graph_trains_on_exact_public_train_and_freezes_state(
    optimizer,
):
    material, allowed, recipe, raw_manifest, files = _graph_case()
    if optimizer == "adam":
        changed = recipe.to_dict()
        changed["procedure"]["configuration"]["training"] = {
            "optimizer": "adam",
            "steps": 1,
            "learning_rate": 0.001,
        }
        recipe = ConstructionRecipe.from_dict(changed)
    inputs, targets = synthetic_graph_adapter.checked_train(
        material["train"], recipe.to_dict()["challenge"]["train_digest"]
    )
    model = synthetic_graph_adapter.build_validated_graph(
        recipe,
        raw_manifest,
        files,
        allowlist_bytes=material["allowlist_bytes"],
        train_cases=len(inputs),
    )
    assert model.params is None
    initial_error = float(np.mean(targets[:4] ** 2))
    fit = model.fit(inputs, targets, seed=7)
    assert fit["train_cases"] == len(inputs)
    assert fit["recipe_digest"] == recipe.digest
    assert np.isfinite(fit["full_train_loss"])
    prediction = model.predict(inputs[:4])
    assert prediction.shape == targets[:4].shape
    assert np.isfinite(prediction).all()
    assert float(np.mean((prediction - targets[:4]) ** 2)) < initial_error
    state = model.frozen_state()
    forward, parameters = bundle_graph_state.load(state, recipe, allowed)
    assert forward == model.forward
    assert len(parameters) == 1
    assert np.isfinite(parameters[0]).all()
    train_digest = recipe.to_dict()["challenge"]["train_digest"]
    with pytest.raises(RecipeRefused, match="train_binding_invalid"):
        synthetic_graph_adapter.checked_train(material["train"] + b"x", train_digest)


def test_graph_adapter_reports_procedure_gap_without_backbone_name_gate():
    _material, _allowed, recipe, _raw_manifest, _files = _graph_case()
    settings = synthetic_graph_adapter.training_settings(recipe, 64)
    assert settings["steps"] == 4
    changed = recipe.to_dict()
    changed["procedure"]["configuration"]["training"]["optimizer"] = "unknown"
    with pytest.raises(RecipeRefused, match="training_adapter_unavailable"):
        synthetic_graph_adapter.training_settings(
            ConstructionRecipe.from_dict(changed), 64
        )
    changed = recipe.to_dict()
    changed["procedure"]["train_use"]["coverage"] = "subset"
    with pytest.raises(RecipeRefused, match="train_use_unavailable"):
        synthetic_graph_adapter.training_settings(
            ConstructionRecipe.from_dict(changed), 64
        )


@pytest.mark.skipif(os.name == "nt", reason="G3 parser needs POSIX rlimits")
def test_graph_train_schedule_uses_fixed_rows_in_declared_update_order():
    material, allowed, recipe, raw_manifest, files = _graph_case()
    first_half = list(range(4))
    all_rows = list(range(8))
    inputs = np.ones((8, 8, 8, 1), dtype=np.float32)
    targets = np.zeros_like(inputs)
    targets[4:] = 2.0

    def fit(schedule):
        changed = recipe.to_dict()
        changed["procedure"]["configuration"]["training"] = {
            "optimizer": "sgd",
            "steps": 2,
            "learning_rate": 0.25,
        }
        changed["procedure"]["train_use"] = {
            "dataset": synthetic_graph_adapter.TRAIN_USE,
            "row_indices_by_step": schedule,
        }
        selected = ConstructionRecipe.from_dict(changed)
        model = synthetic_graph_adapter.build_validated_graph(
            selected,
            raw_manifest,
            files,
            allowlist_bytes=material["allowlist_bytes"],
            train_cases=len(inputs),
        )
        receipt = model.fit(inputs, targets, seed=7)
        state = model.frozen_state()
        _forward, parameters = bundle_graph_state.load(state, selected, allowed)
        return float(parameters[0][0]), receipt, model.predict(inputs[:1])

    scheduled, receipt, prediction = fit([first_half, all_rows])
    all_only, _, _ = fit([all_rows, all_rows])
    reversed_steps, _, _ = fit([all_rows, first_half])
    assert np.isclose(scheduled, 0.5)
    assert np.isclose(all_only, 0.75)
    assert np.isclose(reversed_steps, 0.25)
    assert np.allclose(prediction, scheduled)
    assert np.isclose(receipt["full_train_loss"], 1.25)


@pytest.mark.skipif(os.name == "nt", reason="G3 parser needs POSIX rlimits")
def test_graph_train_schedule_refuses_invalid_or_over_budget_fixed_row_use():
    _material, _allowed, recipe, _raw_manifest, _files = _graph_case()
    changed = recipe.to_dict()
    changed["procedure"]["configuration"]["training"]["steps"] = 2
    for schedule in (
        [[0]],  # One declared update has no row selection.
        [[], [0]],
        [[0], [8]],
        [[0], [True]],
        [[0], list(range(9))],  # More work than the existing all-row update.
    ):
        changed["procedure"]["train_use"] = {
            "dataset": synthetic_graph_adapter.TRAIN_USE,
            "row_indices_by_step": schedule,
        }
        with pytest.raises(RecipeRefused, match="train_use_invalid"):
            synthetic_graph_adapter.training_settings(
                ConstructionRecipe.from_dict(changed), 8
            )


def _build_program_files(material, allowed, recipe, raw_manifest, graph_files):
    source_raw = canonical(staging.envelope(raw_manifest, graph_files))
    named = recipe.to_dict()["challenge"]
    binding = {
        "challenge_id": named["id"],
        "challenge_version": named["version"],
        "train_digest": named["train_digest"],
        "interface_digest": named["interface_digest"],
        "construction_limits_digest": named["construction_limits_digest"],
    }
    files = _stage_modules()
    root = Path(__file__).resolve().parents[2]
    files.update(
        {
            name + ".py": (root / (name.replace(".", "/") + ".py")).read_bytes()
            for name in direct_graph_construction_worker.STAGED_MODULES
        }
    )
    files.update(
        {
            "recipe.json": recipe.canonical_bytes,
            "source-envelope.json": source_raw,
            "train.npz": material["train"],
            "allowlist.json": material["allowlist_bytes"],
            "control.json": canonical(
                {
                    "recipe_digest": recipe.digest,
                    "binding": binding,
                    "submission_digest": recipe.to_dict()["source"][
                        "submission_digest"
                    ],
                    "envelope_digest": _digest(source_raw),
                    "allowlist_digest": allowed.digest,
                    "seed": 7,
                }
            ),
        }
    )
    return files, binding


def _run_program(tmp_path, name, files, program, *, expected_exit=0):
    home = tmp_path / name
    work = home / "workspace"
    work.mkdir(parents=True)
    (home / "output").mkdir()
    for filename, body in files.items():
        (work / filename).write_bytes(body)
    done = subprocess.run(
        [sys.executable, "-c", program],
        cwd=work,
        env={**os.environ, "JAX_PLATFORMS": "cpu"},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if expected_exit is None:
        assert done.returncode != 0
    else:
        assert done.returncode == expected_exit, done.stderr
    return home / "output"


@pytest.mark.skipif(os.name == "nt", reason="G3 parser needs POSIX rlimits")
@pytest.mark.parametrize("optimizer", ["sgd", "adam"])
def test_fixed_graph_program_rebuilds_twice_then_infers_without_source_or_train(
    tmp_path,
    optimizer,
):
    material, allowed, recipe, raw_manifest, graph_files = _graph_case()
    if optimizer == "adam":
        changed = recipe.to_dict()
        changed["procedure"]["configuration"]["training"] = {
            "optimizer": "adam",
            "steps": 1,
            "learning_rate": 0.001,
        }
        recipe = ConstructionRecipe.from_dict(changed)
    build_files, binding = _build_program_files(
        material, allowed, recipe, raw_manifest, graph_files
    )
    first = _run_program(
        tmp_path,
        "build-one",
        build_files,
        direct_graph_construction_worker.BUILD_PROGRAM,
    )
    second = _run_program(
        tmp_path,
        "build-two",
        build_files,
        direct_graph_construction_worker.BUILD_PROGRAM,
    )
    state = (first / "state.npz").read_bytes()
    assert (second / "state.npz").read_bytes() == state
    build_receipt = json.loads((first / "receipt.json").read_bytes())
    assert build_receipt["state_digest"] == _digest(state)
    assert (
        build_receipt["submission_digest"]
        == recipe.to_dict()["source"]["submission_digest"]
    )
    requested = material["practice_inputs"][:2]
    requested_raw = _tensors(inputs=requested)
    infer_files, codec_modules = _stage_bundle_modules(binding, training=False)
    infer_files.update(
        {
            "recipe.json": recipe.canonical_bytes,
            "state.npz": state,
            "inputs.npz": requested_raw,
            "allowlist.json": material["allowlist_bytes"],
            "control.json": canonical(
                {
                    "recipe_digest": recipe.digest,
                    "binding": binding,
                    "codec_modules": codec_modules,
                    "state_digest": _digest(state),
                    "inputs_digest": _digest(requested_raw),
                    "allowlist_digest": allowed.digest,
                    "expected_output_shape": list(requested.shape),
                    "expected_output_dtype": "float32",
                    "input_name": "inputs/forcing",
                }
            ),
        }
    )
    assert "train.npz" not in infer_files
    assert "source-envelope.json" not in infer_files
    inferred = _run_program(tmp_path, "infer", infer_files, INFER_PROGRAM)
    predictions = np.asarray(
        json.loads((inferred / "predictions.json").read_bytes()),
        dtype=np.float32,
    )
    assert predictions.shape == requested.shape
    assert np.isfinite(predictions).all()


@pytest.mark.skipif(os.name == "nt", reason="G3 parser needs POSIX rlimits")
def test_fixed_graph_program_distinguishes_invalid_source_adapter_gap_and_worker_bug(
    tmp_path,
):
    material, allowed, recipe, raw_manifest, graph_files = _graph_case()
    malformed = json.loads(raw_manifest)
    malformed["interface"] = "sha256:" + "0" * 64
    invalid_manifest = canonical(malformed)
    invalid_document = recipe.to_dict()
    invalid_document["source"]["submission_digest"] = submission.digest(malformed)
    invalid_recipe = ConstructionRecipe.from_dict(invalid_document)
    invalid_files, _binding = _build_program_files(
        material, allowed, invalid_recipe, invalid_manifest, graph_files
    )
    invalid_out = _run_program(
        tmp_path,
        "invalid-graph",
        invalid_files,
        direct_graph_construction_worker.BUILD_PROGRAM,
    )
    invalid = json.loads((invalid_out / "outcome.json").read_bytes())
    assert invalid["schema"] == direct_graph_construction_worker.OUTCOME_SCHEMA
    assert invalid["state"] == "REFUSED"
    assert invalid["reason_code"] == "graph_submission_invalid"
    assert not (invalid_out / "state.npz").exists()

    unsupported_document = recipe.to_dict()
    unsupported_document["procedure"]["train_use"]["coverage"] = "subset"
    unsupported_recipe = ConstructionRecipe.from_dict(unsupported_document)
    unsupported_files, _binding = _build_program_files(
        material, allowed, unsupported_recipe, raw_manifest, graph_files
    )
    unsupported_out = _run_program(
        tmp_path,
        "adapter-gap",
        unsupported_files,
        direct_graph_construction_worker.BUILD_PROGRAM,
    )
    unsupported = json.loads((unsupported_out / "outcome.json").read_bytes())
    assert unsupported == {
        "schema": direct_graph_construction_worker.OUTCOME_SCHEMA,
        "state": "UNRESOLVED",
        "reason_code": "carbon_graph_adapter_unavailable",
        "detail_code": "synthetic_graph_train_use_unavailable",
    }
    assert not (unsupported_out / "state.npz").exists()

    broken_files = dict(unsupported_files)
    broken_files["carbon.development_session.synthetic_graph_adapter.py"] = (
        b"raise RuntimeError('fixed-worker-bug')\n"
    )
    broken_out = _run_program(
        tmp_path,
        "worker-bug",
        broken_files,
        direct_graph_construction_worker.BUILD_PROGRAM,
        expected_exit=None,
    )
    assert not (broken_out / "outcome.json").exists()
    assert not (broken_out / "state.npz").exists()

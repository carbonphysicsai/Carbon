"""A noncatalogue mathematical graph uses its own recipe and TRAIN adapter."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.battery import challenge, construction_kit, direct_graph
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)

ROOT = Path(__file__).resolve().parents[2]


def _recipe(submission_digest, *, precision=None):
    training = {"steps": 16, "batch_size": 8}
    if precision is not None:
        training["precision"] = precision
    return ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": {
                "id": challenge.CHALLENGE.challenge_id,
                "version": challenge.CHALLENGE.version,
                "train_digest": "sha256:" + challenge.TRAIN_V1_SHA256,
                "interface_digest": construction_kit.interface_digest(),
                "construction_limits_digest": construction_kit.construction_limits_digest(),
            },
            "source": {"kind": "graph", "submission_digest": submission_digest},
            "procedure": {
                "entrypoint": None,
                "configuration": {"training": training},
                "train_use": {
                    "dataset": direct_graph.TRAIN_USE,
                    "train_fraction": 0.1,
                    "curriculum": "none",
                },
                "initial_state": None,
            },
            "output": {
                "format": direct_graph.OUTPUT_FORMAT,
                "interface_digest": construction_kit.interface_digest(),
            },
        }
    )


def test_direct_graph_training_settings_ignore_backbone_names_and_combinations():
    settings = direct_graph.training_settings(_recipe("sha256:" + "a" * 64))
    assert settings["steps"] == 16
    assert settings["train_fraction"] == 0.1
    assert settings["backend"] == "jax"
    assert direct_graph.graph_interface(settings).inputs[0][2] == (4,)
    assert direct_graph.graph_interface(settings).outputs[0][1] == (247,)


def test_unsupported_training_configuration_refuses_precisely():
    doc = _recipe("sha256:" + "a" * 64).to_dict()
    doc["procedure"]["configuration"]["training"]["backend"] = "pytorch"
    with pytest.raises(RecipeRefused, match="battery_graph_backend_unsupported"):
        direct_graph.training_settings(ConstructionRecipe.from_dict(doc))
    doc["procedure"]["configuration"]["training"]["backend"] = "jax"
    doc["procedure"]["configuration"]["training"]["family"] = "mlp"
    with pytest.raises(RecipeRefused, match="battery_graph_training_field_invalid"):
        direct_graph.training_settings(ConstructionRecipe.from_dict(doc))


@pytest.mark.skipif(
    os.name == "nt", reason="G3 isolated graph parse needs POSIX rlimits"
)
@pytest.mark.parametrize("precision", ["float32", "float64"])
def test_novel_affine_graph_is_rebuilt_and_trained_from_pinned_train(
    tmp_path, precision
):
    import hashlib
    import json
    import shutil
    import subprocess
    import sys
    from types import SimpleNamespace

    import jax
    import jax.numpy as jnp
    import numpy as np

    from carbon.battery import direct_graph_inference, direct_graph_worker
    from carbon.development_session.construction_recipe import (
        graph_envelope_from_workspace,
    )
    from carbon.development_session.research_ledger import VERSION, CampaignLedger
    from carbon.development_session.research_workspace import ResearchWorkspace
    from carbon.level4 import (
        allowlist,
        graph,
        initializers,
        intake,
        staging,
        submission,
    )
    from carbon.level4.tooling import through_bprime

    registry = allowlist.load()
    settings = direct_graph.training_settings(
        _recipe("sha256:" + "a" * 64, precision=precision)
    )
    interface = direct_graph.graph_interface(settings)
    batch = 8
    with jax.enable_x64(precision == "float64"):
        dtype = jnp.float64 if precision == "float64" else jnp.float32
        _, forward, _ = through_bprime(
            lambda w, b, x: x @ w + b,
            (
                jnp.ones((4, 247), dtype),
                jnp.zeros((247,), dtype),
                jnp.ones((batch, 4), dtype),
            ),
            role="forward",
            allowlist=registry,
            input_names=["params/0", "params/1", "inputs/features"],
            max_bytes=intake.BOUNDS["document_bytes"],
        )
    init_spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(forward),
        "parameters": [
            {
                "input": "params/0",
                "initializer": "he_normal",
                "fan_in_axes": [0],
                "fan_out_axes": [1],
            },
            {
                "input": "params/1",
                "initializer": "zeros",
                "fan_in_axes": [],
                "fan_out_axes": [],
            },
        ],
    }
    manifest, files = submission.build(
        challenge=challenge.CHALLENGE.challenge_id,
        interface=interface.digest(),
        allowlist=registry,
        forward=forward,
        init_spec=init_spec,
    )
    raw = submission.canonical(manifest)
    recipe = _recipe(submission.digest(manifest), precision=precision)
    model = direct_graph.build_validated_graph(
        recipe,
        raw,
        files,
        max_bytes=intake.BOUNDS["submission_bytes"],
        train_cases=challenge.TRAIN_V1_CASES,
    )
    material = challenge.PublicMaterial.load(ROOT)
    with jax.enable_x64(False):
        result = model.fit(material.train, seed=7)
        predictions = model.predict(material.train.x[:2])
    assert not jax.config.jax_enable_x64
    assert all(value.dtype == np.dtype(precision) for value in predictions.values())
    assert result["n_params"] == 4 * 247 + 247
    assert result["recipe_digest"] == recipe.digest
    assert predictions["v"].shape == (2, 121)
    assert predictions["q"].shape == (2, 4)
    assert all(np.isfinite(values).all() for values in predictions.values())
    state = direct_graph.frozen_state_bytes(
        model, raw, files, max_bytes=128 * 1024 * 1024
    )
    import io

    with np.load(io.BytesIO(state), allow_pickle=False) as data:
        header = json.loads(bytes(data["__header__"]).decode())
        assert header["recipe_digest"] == recipe.digest
        assert header["submission_digest"] == submission.digest(manifest)
        assert header["parameter_count"] == 2
        assert np.array_equal(data["manifest"], np.frombuffer(raw, dtype=np.uint8))
    with jax.enable_x64(False):
        restored = direct_graph.load_frozen_state(
            state,
            recipe=recipe,
            max_bytes=128 * 1024 * 1024,
            train_cases=challenge.TRAIN_V1_CASES,
        )
        restored_predictions = restored.predict(material.train.x[:2])
    assert not jax.config.jax_enable_x64
    assert all(
        value.dtype == np.dtype(precision) for value in restored_predictions.values()
    )
    for name in predictions:
        np.testing.assert_allclose(restored_predictions[name], predictions[name])
    with pytest.raises(RecipeRefused, match="battery_graph_state_identity_invalid"):
        direct_graph.load_frozen_state(
            state,
            recipe=_recipe("sha256:" + "0" * 64),
            max_bytes=128 * 1024 * 1024,
            train_cases=challenge.TRAIN_V1_CASES,
        )
    inputs = {
        "cases": [
            {
                "case_id": case_id,
                "inputs": dict(zip(challenge.INPUTS, map(float, values))),
            }
            for case_id, values in zip(
                material.train.case_ids[:2], material.train.x[:2]
            )
        ]
    }
    ledger = CampaignLedger(tmp_path / "campaign")
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": {},
            "elapsed_seconds": None,
            "campaign_id": "direct-graph-local-test",
            "implementation": "fixture",
            "objective": "public TRAIN graph reconstruction test",
            "sampling": "fixture",
            "control": "none",
            "selection": "none",
            "replica_policy": "fixture",
            "provider": "none",
            "owner": "fixture",
        }
    )
    workspace = ResearchWorkspace(ledger, "fixture")
    workspace.put(staging.WORKSPACE_MANIFEST, raw)
    for name, body in files.items():
        workspace.put(staging.WORKSPACE_PREFIX + name[7:] + ".json", body)
    source_envelope = graph_envelope_from_workspace(ledger, "fixture", recipe)
    staged = direct_graph_worker.staged_files(
        ROOT,
        recipe,
        source_envelope,
        seed=7,
        test_inputs=inputs,
    )
    assert set(staged) & {"practice.json", "reference.json", "hidden.json"} == set()
    work = tmp_path / "work"
    work.mkdir()
    (tmp_path / "output").mkdir()
    for name, body in staged.items():
        (work / name).write_bytes(body)
    (work / "program.py").write_text(direct_graph_worker.PROGRAM)
    result = subprocess.run(
        [sys.executable, "-I", str(work / "program.py")],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    worker_fit = json.loads((tmp_path / "output" / "fit.json").read_text())
    worker_predictions = json.loads(
        (tmp_path / "output" / "predictions.json").read_text()
    )
    assert worker_fit["recipe_digest"] == recipe.digest
    assert list(worker_predictions) == sorted(
        inputs["cases"][i]["case_id"] for i in range(2)
    )
    assert (tmp_path / "output" / "state.npz").stat().st_size > 0
    inference_files = direct_graph_inference.staged_files(recipe, state, inputs)
    assert "train-v1.jsonl.gz" not in inference_files
    assert not any(name.startswith("level4-doc-") for name in inference_files)
    inference_base = tmp_path / "inference"
    inference_work = inference_base / "work"
    inference_work.mkdir(parents=True)
    inference_output = inference_base / "output"
    inference_output.mkdir()
    for name, body in inference_files.items():
        (inference_work / name).write_bytes(body)
    (inference_work / "program.py").write_text(direct_graph_inference.PROGRAM)
    inference_run = subprocess.run(
        [sys.executable, "-I", str(inference_work / "program.py")],
        cwd=inference_work,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert inference_run.returncode == 0, inference_run.stderr[-4000:]
    separate_predictions = json.loads(
        (inference_output / "predictions.json").read_text()
    )
    assert set(separate_predictions) == set(worker_predictions)
    snapshot = tmp_path / "operation-test" / "snapshot"
    shutil.copytree(tmp_path / "output", snapshot)

    def fake_runner(_ledger, **kwargs):
        kwargs["output_validator"](snapshot)
        return {
            "operation": "operation-test",
            "files": {
                path.name: "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                for path in snapshot.iterdir()
            },
        }

    result = direct_graph_worker.reconstruct_public(
        SimpleNamespace(root=tmp_path),
        owner="test",
        identity="test",
        image=object(),
        root=ROOT,
        recipe=recipe,
        source_envelope=source_envelope,
        seed=7,
        test_inputs=inputs,
        runner=fake_runner,
    )
    assert result.recipe_digest == recipe.digest
    assert result.state_digest == worker_fit["state_sha256"]
    assert set(result.predictions) == {case["case_id"] for case in inputs["cases"]}
    if image_manifest := os.environ.get("CARBON_REAL_C03_MANIFEST"):
        from carbon.reconstruction.worker.docker_runtime import load_image_identity
        from carbon.reconstruction.worker.model import WorkerFailure

        try:
            real = direct_graph_worker.reconstruct_public(
                ledger,
                owner="fixture",
                identity="direct-graph-local-test",
                image=load_image_identity(Path(image_manifest)),
                root=ROOT,
                recipe=recipe,
                source_envelope=source_envelope,
                seed=7,
                test_inputs=inputs,
            )
        except WorkerFailure as error:
            pytest.fail(error.private_diagnostic.decode("utf-8", "replace"))
        assert real.recipe_digest == recipe.digest
        assert real.state_path.is_file()
        assert set(real.predictions) == set(worker_predictions)
        inferred = direct_graph_inference.infer_public(
            ledger,
            owner="fixture",
            identity="direct-graph-infer-test",
            image=load_image_identity(Path(image_manifest)),
            recipe=recipe,
            build=real,
            test_inputs=inputs,
        )
        assert inferred.state_digest == real.state_digest
        assert set(inferred.predictions) == set(real.predictions)
        if evidence_path := os.environ.get("CARBON_S5_EVIDENCE_DIR"):
            evidence = Path(evidence_path)
            evidence.mkdir(parents=True, exist_ok=False, mode=0o700)
            operation = ledger.root / real.worker_operation
            shutil.copytree(operation / "input", evidence / "stage")
            shutil.copytree(operation / "snapshot", evidence / "output")
            inference_operation = ledger.root / inferred.worker_operation
            shutil.copytree(
                inference_operation / "input", evidence / "inference" / "stage"
            )
            shutil.copytree(
                inference_operation / "snapshot", evidence / "inference" / "output"
            )
            shutil.copyfile(image_manifest, evidence / "image-identity.json")
            (evidence / "source-envelope.json").write_bytes(source_envelope)
            with ledger.db() as connection:
                receipt = connection.execute(
                    "SELECT result FROM operations WHERE id=?",
                    ("direct-graph-local-test",),
                ).fetchone()
            assert receipt is not None and receipt[0] is not None
            (evidence / "carrier-receipt.json").write_bytes(receipt[0])
            with ledger.db() as connection:
                inference_receipt = connection.execute(
                    "SELECT result FROM operations WHERE id=?",
                    ("direct-graph-infer-test",),
                ).fetchone()
            assert inference_receipt is not None and inference_receipt[0] is not None
            (evidence / "inference-receipt.json").write_bytes(inference_receipt[0])
            retained = {
                path.relative_to(evidence).as_posix(): "sha256:"
                + hashlib.sha256(path.read_bytes()).hexdigest()
                for path in evidence.rglob("*")
                if path.is_file()
            }
            (evidence / "lineage.json").write_text(
                json.dumps(
                    {
                        "schema": "carbon.battery.direct-graph-local-evidence.v1",
                        "scope": "PUBLIC_DEVELOPMENT_LOCAL_C03",
                        "recipe_digest": recipe.digest,
                        "graph_digest": recipe.to_dict()["source"]["submission_digest"],
                        "train_digest": construction_kit.construction_kit()[
                            "train_digest"
                        ],
                        "image_id": load_image_identity(Path(image_manifest)).image_id,
                        "state_digest": real.state_digest,
                        "operation": real.worker_operation,
                        "inference_operation": inferred.worker_operation,
                        "inference_predictions_digest": inferred.predictions_digest,
                        "retained_files": retained,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
    (snapshot / "fit.json").write_text(
        json.dumps({**worker_fit, "train_digest": "sha256:" + "0" * 64})
    )
    with pytest.raises(ValueError, match="result identity differs"):
        direct_graph_worker.reconstruct_public(
            SimpleNamespace(root=tmp_path),
            owner="test",
            identity="test",
            image=object(),
            root=ROOT,
            recipe=recipe,
            source_envelope=source_envelope,
            seed=7,
            test_inputs=inputs,
            runner=fake_runner,
        )
    wrong = _recipe("sha256:" + "0" * 64)
    with pytest.raises(
        RecipeRefused, match="construction_recipe_graph_digest_mismatch"
    ):
        direct_graph.build_validated_graph(
            wrong,
            raw,
            files,
            max_bytes=intake.BOUNDS["submission_bytes"],
            train_cases=challenge.TRAIN_V1_CASES,
        )

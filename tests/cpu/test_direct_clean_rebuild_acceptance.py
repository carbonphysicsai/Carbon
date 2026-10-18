"""Direct construction CPU acceptance on public synthetic material.

The harness executes the fixed build and inference programs in fresh local
processes and exercises the host custody API. It does not simulate Docker
isolation, GPU admission, protected evaluation, or scientific qualification.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
from dataclasses import replace

import numpy as np
import pytest

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material
from carbon.development_session.bundle_construction_worker import (
    BUILD_PROGRAM,
    INFER_PROGRAM,
    infer_public,
    infer_saved_bundle,
    reconstruct_public,
)
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.development_session.library_bundles import (
    BUNDLE_SCHEMA,
    ProvisionedLibraryEnvironment,
    _environment_digest,
    bundle_ref,
)
from carbon.development_session.research_image import LibraryWorkerImage
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.reconstruction.worker.model import WorkerImageIdentity


def _digest(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


SOURCE = (
    "import numpy as np\n"
    "import jax.numpy as jnp\n"
    "def build(train_inputs, train_targets, *, seed, configuration, train_use):\n"
    "    assert seed == 11 and configuration == {} and train_use == {'cases': 'all'}\n"
    "    scale = np.float32(np.sum(train_inputs * train_targets) / np.sum(train_inputs**2))\n"
    "    return {'framework': 'jax', 'apply': lambda x: x * jnp.asarray(scale), 'parameters': []}\n"
)


def _source_bundle(tmp_path):
    """Validate exact local source closure; installation is a CPU test stand-in."""
    license_text = b"MIT\n"
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, body in (
            ("source/candidate/__init__.py", b""),
            ("source/candidate/build.py", SOURCE.encode()),
            ("source/LICENSE", license_text),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(body)
            archive.addfile(member, io.BytesIO(body))
    source = output.getvalue()
    lock = b""
    base = "sha256:" + "1" * 64
    manifest = {
        "schema": BUNDLE_SCHEMA,
        "name": "synthetic-linear-source",
        "language": "python",
        "source_sha256": _digest(source),
        "source_bytes": len(source),
        "runtime_profile_id": "jax-cuda13-py311",
        "base_environment_digest": base,
        "environment_digest": _environment_digest(base, _digest(lock)),
        "os": "linux",
        "architecture": "amd64",
        "python_abi": "cp311",
        "accelerator": "cuda13",
        "lock_sha256": _digest(lock),
        "wheels": {},
        "license_sha256": _digest(license_text),
    }
    reference = bundle_ref(manifest, source, {}, lock, license_text)
    installed = tmp_path / "installed"
    (installed / "candidate").mkdir(parents=True)
    (installed / "candidate" / "__init__.py").write_bytes(b"")
    (installed / "candidate" / "build.py").write_bytes(SOURCE.encode())
    pin = "sha256:" + "2" * 64
    parent = WorkerImageIdentity(*(pin for _ in range(8)))
    provisioned = ProvisionedLibraryEnvironment(
        reference, parent.image_id, tmp_path, _digest(source), "sha256:" + "3" * 64
    )
    image = LibraryWorkerImage(provisioned, parent, reference.to_dict())
    return image, installed


def _recipe(material, image):
    return ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": material["construction_kit"],
            "source": {"kind": "bundle", "bundle_ref": image.bundle_ref},
            "procedure": {
                "entrypoint": {"module": "candidate.build", "name": "build"},
                "configuration": {},
                "train_use": {"cases": "all"},
                "initial_state": None,
            },
            "output": {
                "format": "carbon.numeric-graph.v1",
                "interface_digest": material["construction_kit"]["interface_digest"],
            },
        }
    )


def _binding(material):
    kit = material["construction_kit"]
    return {
        "challenge_id": kit["id"],
        "challenge_version": kit["version"],
        "train_digest": kit["train_digest"],
        "interface_digest": kit["interface_digest"],
        "construction_limits_digest": kit["construction_limits_digest"],
    }


def test_direct_task_accepts_distinct_construction_and_inference_parents(tmp_path):
    image, _ = _source_bundle(tmp_path)
    provider = object.__new__(DirectDevelopmentTasksV3)
    provider.image = image
    provider.inference_image = WorkerImageIdentity(
        *("sha256:" + "4" * 64 for _ in range(8))
    )
    provider.image_resolver = None
    provider._check_image_identity()


class LocalProcessRunner:
    """Run actual fixed programs, preserving the host API's snapshot contract."""

    def __init__(self, installed):
        self.installed = installed
        self.calls = []

    def __call__(self, ledger, **request):
        source = request["source"]
        assert source in (BUILD_PROGRAM, INFER_PROGRAM)
        construction = source == BUILD_PROGRAM
        assert request["provenance"] == (
            "DIRECT_BUNDLE_PUBLIC_RECONSTRUCTION"
            if construction
            else "DIRECT_BUNDLE_PUBLIC_INFERENCE"
        )
        if construction:
            assert type(request["image"]) is LibraryWorkerImage
            assert "train.npz" in request["files"]
        else:
            assert type(request["image"]) is WorkerImageIdentity
            assert "train.npz" not in request["files"]
            assert not any("candidate" in name for name in request["files"])
            assert "source.tar.gz" not in request["files"]
        number = len(self.calls) + 1
        operation = f"operation-{number}"
        root = ledger.root / operation
        workspace = root / "workspace"
        snapshot = root / "snapshot"
        workspace.mkdir(parents=True)
        snapshot.mkdir()
        (root / "output").mkdir()
        for name, body in request["files"].items():
            (workspace / name).write_bytes(body)
        env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        if construction:
            env["PYTHONPATH"] = str(self.installed)
        result = subprocess.run(
            [sys.executable, "-c", source],
            cwd=workspace,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        for path in (root / "output").iterdir():
            shutil.copyfile(path, snapshot / path.name)
        request["output_validator"](snapshot)
        self.calls.append((source, frozenset(request["files"]), request["image"]))
        return {
            "operation": operation,
            "files": {
                path.name: _digest(path.read_bytes()) for path in snapshot.iterdir()
            },
        }


def test_fixed_train_clean_rebuild_then_source_free_public_inference(tmp_path):
    material = bundle_material()
    image, installed = _source_bundle(tmp_path)
    recipe = _recipe(material, image)
    ledger = CampaignLedger(tmp_path / "campaign")
    runner = LocalProcessRunner(installed)
    build_args = {
        "owner": "miner",
        "image": image,
        "recipe": recipe,
        "challenge_binding": _binding(material),
        "train": material["train"],
        "example": material["example"],
        "seed": 11,
        "allowlist_bytes": material["allowlist_bytes"],
        "runner": runner,
    }
    first = reconstruct_public(ledger, identity="first", **build_args)
    second = reconstruct_public(ledger, identity="clean-rebuild", **build_args)
    assert first.worker_operation != second.worker_operation
    assert first.receipt == second.receipt
    assert first.receipt["recipe_digest"] == recipe.digest
    assert first.receipt["train_digest"] == material["construction_kit"]["train_digest"]
    assert first.state_digest == second.state_digest
    assert first.state_path.read_bytes() == second.state_path.read_bytes()

    inferred = infer_public(
        ledger,
        owner="miner",
        identity="practice-inference",
        image=image,
        inference_image=image.parent,
        recipe=recipe,
        challenge_binding=_binding(material),
        build=second,
        inputs=material["practice_inputs"],
        expected_output_shape=material["expected_output_shape"],
        allowlist_bytes=material["allowlist_bytes"],
        runner=runner,
    )
    assert inferred.recipe_digest == first.recipe_digest
    assert inferred.state_digest == second.state_digest
    assert inferred.receipt["schema"] == "carbon.development.bundle-inference.v1"
    assert "measurement" not in inferred.receipt
    np.testing.assert_allclose(
        inferred.predictions, material["practice_reference"], rtol=0, atol=1e-6
    )
    assert len(runner.calls) == 3
    assert runner.calls[2][0] == INFER_PROGRAM
    assert runner.calls[2][2] == image.parent
    assert "train.npz" not in runner.calls[2][1]


def test_unmeasured_inference_rejects_shape_correct_wrong_dtype(tmp_path):
    material = bundle_material()
    image, installed = _source_bundle(tmp_path)
    recipe = _recipe(material, image)
    ledger = CampaignLedger(tmp_path / "campaign")
    runner = LocalProcessRunner(installed)
    built = reconstruct_public(
        ledger,
        owner="miner",
        identity="wrong-dtype-build",
        image=image,
        recipe=recipe,
        challenge_binding=_binding(material),
        train=material["train"],
        example=material["example"],
        seed=11,
        allowlist_bytes=material["allowlist_bytes"],
        runner=runner,
    )
    # The valid bundle emits float32 with the expected shape. An int32
    # contract must reject that output even without measurement.
    with pytest.raises(
        AssertionError, match="bundle inference output contract differs"
    ):
        infer_public(
            ledger,
            owner="miner",
            identity="wrong-dtype-inference",
            image=image,
            inference_image=image.parent,
            recipe=recipe,
            challenge_binding=_binding(material),
            build=built,
            inputs=material["practice_inputs"],
            expected_output_shape=material["expected_output_shape"],
            expected_output_dtype="int32",
            allowlist_bytes=material["allowlist_bytes"],
            runner=runner,
        )


def test_changed_train_recipe_image_or_state_refuses_before_inference(tmp_path):
    material = bundle_material()
    image, installed = _source_bundle(tmp_path)
    recipe = _recipe(material, image)
    submitted_state = recipe.to_dict()
    submitted_state["procedure"]["initial_state"] = {"weights": [0.25]}
    with pytest.raises(
        RecipeRefused, match="construction_recipe_pretrained_state_forbidden"
    ):
        ConstructionRecipe.from_dict(submitted_state)
    ledger = CampaignLedger(tmp_path / "campaign")
    runner = LocalProcessRunner(installed)
    common = {
        "owner": "miner",
        "image": image,
        "recipe": recipe,
        "challenge_binding": _binding(material),
        "example": material["example"],
        "seed": 11,
        "allowlist_bytes": material["allowlist_bytes"],
        "runner": runner,
    }
    with pytest.raises(RecipeRefused, match="bundle_build_binding_invalid"):
        reconstruct_public(
            ledger, identity="changed-train", train=material["train"] + b"x", **common
        )
    with pytest.raises(RecipeRefused, match="bundle_build_binding_invalid"):
        reconstruct_public(
            ledger,
            identity="changed-image",
            train=material["train"],
            **{
                **common,
                "image": replace(
                    image,
                    bundle_ref={**image.bundle_ref, "bundle_digest": _digest(b"other")},
                ),
            },
        )
    assert runner.calls == []

    built = reconstruct_public(
        ledger, identity="original", train=material["train"], **common
    )
    changed = recipe.to_dict()
    changed["procedure"]["train_use"] = {"cases": "other"}
    with pytest.raises(RecipeRefused, match="bundle_inference_custody_invalid"):
        infer_public(
            ledger,
            owner="miner",
            identity="changed-recipe",
            image=image,
            inference_image=image.parent,
            recipe=ConstructionRecipe.from_dict(changed),
            challenge_binding=_binding(material),
            build=built,
            inputs=material["practice_inputs"],
            expected_output_shape=material["expected_output_shape"],
            allowlist_bytes=material["allowlist_bytes"],
            runner=runner,
        )
    built.state_path.write_bytes(built.state_path.read_bytes() + b"x")
    with pytest.raises(RecipeRefused, match="bundle_inference_state_changed"):
        infer_public(
            ledger,
            owner="miner",
            identity="changed-state",
            image=image,
            inference_image=image.parent,
            recipe=recipe,
            challenge_binding=_binding(material),
            build=built,
            inputs=material["practice_inputs"],
            expected_output_shape=material["expected_output_shape"],
            allowlist_bytes=material["allowlist_bytes"],
            runner=runner,
        )
    assert len(runner.calls) == 1


def test_saved_graph_inference_preserves_exact_tensor_contract_and_source_boundary(
    tmp_path,
):
    material = bundle_material()
    image, installed = _source_bundle(tmp_path)
    recipe = _recipe(material, image)
    ledger = CampaignLedger(tmp_path / "campaign")
    runner = LocalProcessRunner(installed)
    built = reconstruct_public(
        ledger,
        owner="miner",
        identity="build",
        image=image,
        recipe=recipe,
        challenge_binding=_binding(material),
        train=material["train"],
        example=material["example"],
        seed=11,
        allowlist_bytes=material["allowlist_bytes"],
        runner=runner,
    )
    state = built.state_path.read_bytes()
    inputs = material["practice_inputs"]
    common = {
        "owner": "miner",
        "image": image,
        "inference_image": image.parent,
        "recipe": recipe,
        "challenge_binding": _binding(material),
        "state_bytes": state,
        "expected_state_digest": built.state_digest,
        "inputs": inputs,
        "expected_input_shape": inputs.shape,
        "expected_input_dtype": str(inputs.dtype),
        "expected_output_shape": tuple(material["expected_output_shape"]),
        "expected_output_dtype": str(np.asarray(material["practice_reference"]).dtype),
        "allowlist_bytes": material["allowlist_bytes"],
        "runner": runner,
    }
    with pytest.raises(RecipeRefused, match="saved_bundle_inference_state_changed"):
        infer_saved_bundle(
            ledger,
            identity="changed-state",
            **{**common, "state_bytes": state + b"x"},
        )
    with pytest.raises(
        RecipeRefused, match="saved_bundle_inference_tensor_contract_invalid"
    ):
        infer_saved_bundle(
            ledger,
            identity="wrong-batch",
            **{**common, "expected_input_shape": (1, *inputs.shape[1:])},
        )
    with pytest.raises(
        RecipeRefused, match="saved_bundle_inference_tensor_contract_invalid"
    ):
        infer_saved_bundle(
            ledger,
            identity="wrong-input-dtype",
            **{**common, "expected_input_dtype": "float64"},
        )
    with pytest.raises(RecipeRefused, match="saved_bundle_inference_binding_invalid"):
        infer_saved_bundle(
            ledger,
            identity="wrong-inference-image",
            **{
                **common,
                "inference_image": image,
            },
        )
    with pytest.raises(RecipeRefused, match="bundle_allowlist_unregistered"):
        infer_saved_bundle(
            ledger,
            identity="untrusted-allowlist",
            **{**common, "allowlist_bytes": b"{}"},
        )
    assert len(runner.calls) == 1

    result = infer_saved_bundle(ledger, identity="saved-inference", **common)
    np.testing.assert_allclose(
        result.predictions, material["practice_reference"], rtol=0, atol=1e-6
    )
    assert result.state_digest == built.state_digest
    assert result.receipt["schema"] == "carbon.development.bundle-inference.v2"
    measurement = result.receipt["measurement"]
    assert (
        measurement["scope"]
        == "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE"
    )
    assert measurement["input_shape"] == list(inputs.shape)
    assert measurement["input_dtype"] == str(inputs.dtype)
    assert measurement["output_shape"] == list(material["expected_output_shape"])
    assert measurement["output_dtype"] == common["expected_output_dtype"]
    assert set(measurement["timing_s"]) == {
        "preprocess",
        "inference",
        "postprocess",
        "export",
    }
    assert all(value >= 0 for value in measurement["timing_s"].values())
    assert sum(measurement["timing_s"].values()) > 0
    assert "peak_memory_bytes" not in measurement
    assert len(runner.calls) == 2
    assert runner.calls[1][0] == INFER_PROGRAM
    assert runner.calls[1][2] == image.parent
    assert "train.npz" not in runner.calls[1][1]
    assert "source.tar.gz" not in runner.calls[1][1]
    alternate_inference = WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8)))
    alternate = infer_saved_bundle(
        ledger,
        identity="distinct-inference-parent",
        **{**common, "inference_image": alternate_inference},
    )
    assert alternate.state_digest == built.state_digest
    assert runner.calls[2][2] == alternate_inference
    assert "train.npz" not in runner.calls[2][1]
    assert "source.tar.gz" not in runner.calls[2][1]

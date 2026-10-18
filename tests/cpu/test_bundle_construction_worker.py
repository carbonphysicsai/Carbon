"""A bundled callable builds on TRAIN, then only inert state enters inference."""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import carbon.development_session.bundle_construction_worker as bundle_worker
from carbon.development_session.bundle_construction_worker import (
    BUILD_PROGRAM,
    INFER_PROGRAM,
    _checked_binding,
    _digest,
    _stage_modules,
    _tensors,
    _trusted_allowlist,
    direct_child_identity,
)
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.development_session.library_bundles import (
    LibraryBundleRef,
    ProvisionedLibraryEnvironment,
)
from carbon.development_session.research_carrier import MINER_GPU
from carbon.development_session.research_image import LibraryWorkerImage
from carbon.level4 import allowlist
from carbon.reconstruction.worker.model import WorkerImageIdentity


def _sha(char):
    return "sha256:" + char * 64


def _recipe(train_digest):
    return ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": {
                "id": "public-field-fixture",
                "version": "development-v1",
                "train_digest": train_digest,
                "interface_digest": _sha("b"),
                "construction_limits_digest": _sha("c"),
            },
            "source": {
                "kind": "bundle",
                "bundle_ref": {
                    "schema": "carbon.library-bundle-ref.v1",
                    "bundle_digest": _sha("d"),
                    "language": "python",
                    "runtime_profile_id": "jax-cuda13-py311",
                    "environment_digest": _sha("e"),
                },
            },
            "procedure": {
                "entrypoint": {"module": "candidate.build", "name": "build"},
                "configuration": {},
                "train_use": {},
                "initial_state": None,
            },
            "output": {
                "format": "carbon.numeric-graph.v1",
                "interface_digest": _sha("b"),
            },
        }
    )


def _binding(recipe):
    row = recipe.to_dict()["challenge"]
    return {
        "challenge_id": row["id"],
        "challenge_version": row["version"],
        "train_digest": row["train_digest"],
        "interface_digest": row["interface_digest"],
        "construction_limits_digest": row["construction_limits_digest"],
    }


def _stage(root, files):
    work = root / "workspace"
    work.mkdir(parents=True)
    (root / "output").mkdir()
    for name, body in files.items():
        (work / name).write_bytes(body)
    return work


def test_host_refuses_recipe_echo_as_trusted_challenge_or_custom_allowlist():
    recipe = _recipe(_sha("a"))
    with pytest.raises(RecipeRefused, match="binding_mismatch"):
        _checked_binding(recipe, {**_binding(recipe), "train_digest": _sha("f")})
    with pytest.raises(RecipeRefused, match="allowlist_unregistered"):
        _trusted_allowlist(allowlist.load().raw + b" ")


def test_host_selects_exact_prospective_v3_allowlist_only():
    from carbon.challenge_kit import synthetic_linear_field_2d as fixture

    raw = fixture.allowlist_v3_bytes()
    assert (
        _trusted_allowlist(raw).digest
        == fixture.bundle_material_v3()["allowlist_digest"]
    )
    with pytest.raises(RecipeRefused, match="allowlist_unregistered"):
        _trusted_allowlist(raw + b" ")


def test_host_selects_exact_prospective_v4_allowlist_only():
    from carbon.challenge_kit import synthetic_linear_field_2d as fixture

    raw = fixture.allowlist_v4_bytes()
    assert (
        _trusted_allowlist(raw).digest
        == fixture.bundle_material_v4()["allowlist_digest"]
    )
    with pytest.raises(RecipeRefused, match="allowlist_unregistered"):
        _trusted_allowlist(raw + b" ")


def test_direct_child_identities_are_stable_distinct_and_within_ledger_bound():
    long_task = "task-" + "a" * 123
    build = direct_child_identity(long_task, "build")
    inference = direct_child_identity(long_task, "inference")
    prep = direct_child_identity(long_task, "prep")
    assert build == direct_child_identity(long_task, "build")
    assert len({prep, build, inference}) == 3
    assert all(len(item) <= 128 for item in (prep, build, inference))
    with pytest.raises(RecipeRefused, match="bundle_child_identity_invalid"):
        direct_child_identity(long_task, "unknown")


@pytest.mark.parametrize("accelerator", [None, MINER_GPU])
def test_composed_bundle_forwards_only_explicit_selected_gpu(monkeypatch, accelerator):
    recipe = _recipe(_sha("a"))
    calls = []
    state_digest = _sha("f")
    build = bundle_worker.BundleBuildResult(
        recipe.digest, state_digest, Path("unused-state.npz"), "build-operation", {}
    )
    inference = bundle_worker.BundleInferenceResult(
        recipe.digest, state_digest, _sha("e"), [], "infer-operation", {}
    )

    def build_phase(ledger, **kwargs):
        calls.append(("build", kwargs))
        return build

    def infer_phase(ledger, **kwargs):
        calls.append(("infer", kwargs))
        return inference

    monkeypatch.setattr(bundle_worker, "reconstruct_public", build_phase)
    monkeypatch.setattr(bundle_worker, "infer_public", infer_phase)
    monkeypatch.setattr(
        bundle_worker,
        "verify_direct_resource_policy",
        lambda binding, limits: _sha("c"),
    )
    policy = {
        "reconstruction_resource_policy": {
            "build_wall_seconds_max": 600,
            "inference_wall_seconds_max": 600,
            "total_reconstruction_wall_seconds_max": 1800,
        }
    }
    result = bundle_worker.reconstruct_and_infer_public(
        object(),
        owner="operator",
        identity="task",
        image=object(),
        inference_image=object(),
        recipe=recipe,
        challenge_binding=_binding(recipe),
        limits_document=policy,
        train=b"training",
        example=np.zeros((1, 1), dtype=np.float32),
        seed=0,
        inputs=np.zeros((1, 1), dtype=np.float32),
        expected_output_shape=(1, 1),
        allowlist_bytes=b"allowlist",
        accelerator=accelerator,
        runner=object(),
    )
    assert result.execution_boundary == "TEST_ONLY_LOCAL_RUNNER"
    assert [phase for phase, _ in calls] == ["build", "infer"]
    assert all((kwargs.get("accelerator") == accelerator) for _, kwargs in calls)
    assert all(
        ("accelerator" in kwargs) == (accelerator is not None) for _, kwargs in calls
    )
    with pytest.raises(RecipeRefused, match="bundle_accelerator_invalid"):
        bundle_worker._accelerator_kwargs("unregistered-device")


def test_gpu_build_refuses_library_child_before_carrier_reservation():
    train = b"registered-public-train"
    recipe = _recipe(_digest(train))
    ref = recipe.to_dict()["source"]["bundle_ref"]
    parent_id = _sha("a")
    parent = WorkerImageIdentity(*(parent_id for _ in range(8)))
    image = LibraryWorkerImage(
        ProvisionedLibraryEnvironment(
            LibraryBundleRef.from_dict(ref),
            parent.image_id,
            Path("unused-context"),
            _sha("b"),
            _sha("c"),
        ),
        parent,
        ref,
    )
    with pytest.raises(RecipeRefused, match="bundle_gpu_overlay_required"):
        bundle_worker.reconstruct_public(
            object(),
            owner="operator",
            identity="task",
            image=image,
            recipe=recipe,
            challenge_binding=_binding(recipe),
            train=train,
            example=np.zeros((1, 1), dtype=np.float32),
            seed=0,
            allowlist_bytes=allowlist.load().raw,
            accelerator=MINER_GPU,
            runner=lambda *_args, **_kwargs: pytest.fail("reached carrier"),
        )


def test_fixed_bundle_build_consumes_train_and_separate_inference_gets_inputs_only(
    tmp_path,
):
    library = tmp_path / "installed-library"
    candidate = library / "candidate"
    candidate.mkdir(parents=True)
    (candidate / "__init__.py").write_text("")
    (candidate / "build.py").write_text(
        "import numpy as np\n"
        "import jax.numpy as jnp\n"
        "def build(train_inputs, train_targets, *, seed, configuration, train_use):\n"
        "    assert seed == 7 and configuration == {} and train_use == {}\n"
        "    scale = np.float32(np.sum(train_targets * train_inputs) / np.sum(train_inputs ** 2))\n"
        "    return {'framework': 'jax', 'apply': lambda x: x * jnp.asarray(scale), 'parameters': []}\n"
    )
    x = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    train = _tensors(inputs=x, targets=3 * x)
    example = _tensors(inputs=x)
    recipe = _recipe(_digest(train))
    allowed = allowlist.load(Path(allowlist.PATH).with_name("allowlist_v2.json"))
    build_files = _stage_modules()
    build_files.update(
        {
            "recipe.json": recipe.canonical_bytes,
            "train.npz": train,
            "example.npz": example,
            "allowlist.json": allowed.raw,
            "control.json": json.dumps(
                {
                    "recipe_digest": recipe.digest,
                    "bundle_ref": recipe.to_dict()["source"]["bundle_ref"],
                    "binding": _binding(recipe),
                    "example_digest": _digest(example),
                    "allowlist_digest": allowed.digest,
                    "seed": 7,
                },
                sort_keys=True,
            ).encode(),
        }
    )
    build_work = _stage(tmp_path / "build", build_files)
    build_env = {**os.environ, "PYTHONPATH": str(library)}
    built = subprocess.run(
        [sys.executable, "-c", BUILD_PROGRAM],
        cwd=build_work,
        env=build_env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert built.returncode == 0, built.stderr
    state = (build_work.parent / "output/state.npz").read_bytes()
    build_receipt = json.loads((build_work.parent / "output/receipt.json").read_bytes())
    assert build_receipt["state_digest"] == _digest(state)
    assert build_receipt["framework"] == "jax"

    rebuilt_work = _stage(tmp_path / "independent-rebuild", build_files)
    rebuilt = subprocess.run(
        [sys.executable, "-c", BUILD_PROGRAM],
        cwd=rebuilt_work,
        env=build_env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert rebuilt.returncode == 0, rebuilt.stderr
    assert (rebuilt_work.parent / "output/state.npz").read_bytes() == state

    requested = _tensors(inputs=np.asarray([[5.0, 6.0], [7.0, 8.0]], dtype=np.float32))
    infer_files = _stage_modules()
    infer_files.update(
        {
            "recipe.json": recipe.canonical_bytes,
            "state.npz": state,
            "inputs.npz": requested,
            "allowlist.json": allowed.raw,
            "control.json": json.dumps(
                {
                    "recipe_digest": recipe.digest,
                    "binding": _binding(recipe),
                    "state_digest": _digest(state),
                    "inputs_digest": _digest(requested),
                    "allowlist_digest": allowed.digest,
                    "expected_output_shape": [2, 2],
                },
                sort_keys=True,
            ).encode(),
        }
    )
    assert "train.npz" not in infer_files
    assert "candidate.build.py" not in infer_files
    infer_work = _stage(tmp_path / "infer", infer_files)
    inferred = subprocess.run(
        [sys.executable, "-c", INFER_PROGRAM],
        cwd=infer_work,
        env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert inferred.returncode == 0, inferred.stderr
    predictions = json.loads(
        (infer_work.parent / "output/predictions.json").read_bytes()
    )
    np.testing.assert_allclose(predictions, [[15.0, 18.0], [21.0, 24.0]])
    receipt = json.loads((infer_work.parent / "output/receipt.json").read_bytes())
    assert receipt["state_digest"] == build_receipt["state_digest"]

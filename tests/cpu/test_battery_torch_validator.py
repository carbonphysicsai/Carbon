"""The PyTorch backend on the validator and miner ends (RECON-TORCH-01).

OWNER-PYTORCH-BACKEND-01: the validator rebuilds a recipe in the worker image
of the backend it names, and scores it like any other. These tests hold:
- the carrier dispatches by backend, and a JAX-only deployment is unchanged;
- a validator without a PyTorch image answers `backend_not_served`, records
  nothing and never blames the miner;
- an image that lacks the backend is infrastructure, not a candidate failure;
- the deployment binds the PyTorch image to its JAX parent and to this
  checkout's exact-hashed science-torch export;
- the image's export pins exactly the contract's dependency pins;
- end to end, a PyTorch recipe is admitted, rebuilt and scored.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest
import tomllib

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import (
    Counting,
    make,
    refs,  # noqa: F401 - fixture
    run,
    submission,
)

from carbon.battery import deployment, worker
from carbon.battery.compile import compile_recipe
from carbon.battery.daemon import BackendNotServed
from carbon.battery.research import image_backends
from carbon.reconstruction import torch_profile
from carbon.reconstruction.worker.model import WorkerImageIdentity

needs_torch = pytest.mark.skipif(
    os.environ.get("CARBON_REQUIRE_TORCH") != "1"
    and (
        importlib.util.find_spec("torch") is None
        or importlib.util.find_spec("neuralop") is None
    ),
    reason="the science-torch group is not installed",
)

TORCH_MLP = {"backend": "pytorch", "width": 16, "depth": 1, "steps": 32}


def image(tag, *, base="0", lock=None):
    digest = "sha256:" + tag * 64
    return WorkerImageIdentity(
        image_id=digest,
        config_digest=digest,
        source_tree_digest="sha256:" + "a" * 64,
        wheel_digest="sha256:" + "b" * 64,
        lock_digest=lock or "sha256:" + "c" * 64,
        base_image_digest="sha256:" + base * 64,
        build_recipe_digest="sha256:" + "d" * 64,
        entrypoint_digest="sha256:" + "e" * 64,
    )


def recipe(backbone="mlp", **parameters):
    strategy = submission("hk", backbone, **parameters).strategy
    return compile_recipe(strategy)[1]


# --- The carrier dispatches by backend. ---


class Stop(Exception):
    pass


def carrier(tmp_path, torch_image=None):
    from carbon.battery.pool_store import PoolStore

    seen = []

    def runner(ledger, **kwargs):
        seen.append(kwargs["image"].image_id)
        raise Stop

    tmp_path.chmod(0o700)
    backend = worker.CarrierBackend(
        worker.WorkLedger(PoolStore(tmp_path / "s.sqlite3"), tmp_path / "work"),
        image("1"),
        torch_image=torch_image,
        root=REPOSITORY,
        runner=runner,
    )
    return backend, seen


def test_a_jax_only_carrier_keeps_its_identity_and_serves_jax(tmp_path):
    backend, seen = carrier(tmp_path)
    assert backend.backends == ("jax",)
    assert backend.identity == {
        "backend": "ISOLATED_CARRIER",
        "validator_path": True,
        "image": "sha256:" + "1" * 64,
    }
    with pytest.raises(worker.WorkerFailure) as failed:
        backend.reconstruct("rec-1", recipe("mlp", width=16), 0)
    assert seen == ["sha256:" + "1" * 64]
    assert failed.value.candidate is False


def test_the_carrier_rebuilds_in_the_image_of_the_recipe_backend(tmp_path):
    backend, seen = carrier(tmp_path, torch_image=image("2", base="1"))
    assert backend.backends == ("jax", "pytorch")
    assert backend.identity["pytorch_image"] == "sha256:" + "2" * 64
    for chosen in (recipe("mlp", width=16), recipe("mlp", **TORCH_MLP), recipe("knn")):
        with pytest.raises(worker.WorkerFailure):
            backend.reconstruct("rec-" + str(len(seen)), chosen, 0)
    assert seen == ["sha256:" + c * 64 for c in "121"]


def test_an_unserved_backend_in_the_carrier_is_never_the_candidates(tmp_path):
    backend, _ = carrier(tmp_path)
    with pytest.raises(worker.WorkerFailure) as failed:
        backend.reconstruct("rec-1", recipe("mlp", **TORCH_MLP), 0)
    assert failed.value.code == "backend_not_served:pytorch"
    assert failed.value.candidate is False


def test_a_worker_image_without_the_backend_is_infrastructure(tmp_path):
    backend, _ = carrier(tmp_path)
    snapshot = backend.ledger.root / "op-1" / "snapshot"
    snapshot.mkdir(parents=True)
    body = json.dumps({"stage": "environment", "error": "ModuleNotFoundError"})
    (snapshot / "failure.json").write_text(body)
    result = {
        "operation": "op-1",
        "files": {"failure.json": worker._digest(body.encode())},
    }
    with pytest.raises(worker.WorkerFailure) as failed:
        backend._snapshot(result, {"state.npz": 1})
    assert failed.value.candidate is False
    body = json.dumps({"stage": "reconstruct", "error": "FloatingPointError"})
    (snapshot / "failure.json").write_text(body)
    result["files"]["failure.json"] = worker._digest(body.encode())
    with pytest.raises(worker.WorkerFailure) as failed:
        backend._snapshot(result, {"state.npz": 1})
    assert failed.value.candidate is True


def test_the_reconstruct_program_reports_a_missing_backend_as_environment():
    program = worker.RECONSTRUCT_PROGRAM
    assert program.index("except ImportError") < program.index("except Exception")
    assert '"stage": "environment"' in program
    for staged in ("battery-torch-training.py", "battery-torch-families.py"):
        assert staged in program and staged in worker.INFER_PROGRAM


# --- Admission. ---


def test_a_validator_without_pytorch_does_not_admit_a_pytorch_recipe(
    tmp_path, refs  # noqa: F811
):
    jax_only = Counting(REPOSITORY)
    jax_only.backends = ("jax",)
    validator = make(tmp_path, refs, jax_only)
    with pytest.raises(BackendNotServed) as missing:
        validator.admit(submission("hk1", "mlp", **TORCH_MLP))
    assert missing.value.backend == "pytorch"
    # Nothing is recorded: the miner may submit it where PyTorch is served.
    assert validator.store.pool()["admitted"] == 0
    with validator.store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM submissions").fetchone() == (0,)
    validator.lock_path = str(tmp_path / "state.lock")
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.evaluate(validator, submission("hk1", "mlp", **TORCH_MLP))
    assert refused.value.code == "backend_not_served"


# --- Deployment. ---


def _config(tmp_path, **overrides):
    from test_battery_validator_deployment import config

    return config(tmp_path, **overrides)


def test_a_torch_manifest_needs_the_carrier(tmp_path):
    path = _config(tmp_path, torch_image_manifest=str(tmp_path / "t.json"))
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.validator(path, repository=REPOSITORY)
    assert refused.value.code == "evaluation_config_image"


@pytest.mark.parametrize("wrong", ["parent", "lock"])
def test_the_torch_image_is_bound_to_its_parent_and_its_export(
    tmp_path, monkeypatch, wrong
):
    from carbon.reconstruction.worker import docker_runtime

    jax_image = image("1")
    torch_image = image(
        "2",
        base="9" if wrong == "parent" else "1",
        lock=(
            None if wrong == "lock" else torch_profile.requirements_digest(REPOSITORY)
        ),
    )
    images = {"jax.json": jax_image, "torch.json": torch_image}
    monkeypatch.setattr(
        docker_runtime, "load_image_identity", lambda path: images[path.name]
    )
    path = _config(
        tmp_path,
        backend="carrier",
        image_manifest=str(tmp_path / "jax.json"),
        torch_image_manifest=str(tmp_path / "torch.json"),
    )
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.validator(path, repository=REPOSITORY)
    assert refused.value.code == "evaluation_config_image"


# --- The miner end and the image's pins. ---


def test_practice_serves_pytorch_only_in_the_pytorch_worker_image():
    assert image_backends(image("1"), REPOSITORY) == ("jax",)
    torch_image = image("2", lock=torch_profile.requirements_digest(REPOSITORY))
    assert image_backends(torch_image, REPOSITORY) == ("jax", "pytorch")


def test_the_torch_image_export_pins_exactly_the_contract_pins():
    """The image installs the exact versions the contract's environment pin
    names, and they are the versions uv.lock resolves."""
    text = (REPOSITORY / torch_profile.REQUIREMENTS_PATH).read_text()
    exported = {}
    for line in text.splitlines():
        if "==" in line and not line.startswith((" ", "#")):
            name, version = line.split(" ;")[0].split("==")
            exported[name] = version
    lock = tomllib.loads((REPOSITORY / "uv.lock").read_text())
    locked = {p["name"]: p["version"] for p in lock["package"]}
    for name, version, source in torch_profile.PINS:
        build = source.split("==")[1]
        assert exported[name] == build, name
        assert locked[name] == build, name
        assert build.split("+")[0] == version
    # Every exported requirement is hash-pinned.
    entries = [e for e in re.split(r"\n(?=\S)", text) if "==" in e.split("\n")[0]]
    assert len(entries) == len(exported)
    assert all("--hash=sha256:" in entry for entry in entries)


def test_the_dockerfile_installs_the_export_with_hashes_only():
    recipe_text = (REPOSITORY / ".devcontainer/torch/Dockerfile").read_text()
    assert "--require-hashes" in recipe_text and "--no-deps" in recipe_text
    assert torch_profile.REQUIREMENTS_PATH in recipe_text
    assert "USER 65532:65532" in recipe_text


# --- End to end. ---


@needs_torch
def test_a_pytorch_recipe_is_admitted_rebuilt_and_scored(tmp_path, refs):  # noqa: F811
    validator = make(tmp_path, refs, Counting(REPOSITORY))
    outcome = run(validator, submission("hk1", "mlp", **TORCH_MLP))
    assert outcome["state"] == "SCORED", outcome
    state = validator.store.model_state(outcome["submission_id"])
    assert state["reconstruction"]["fit"]["backend"] == "pytorch"
    assert worker.state_backend(state["state"]) == "pytorch"
    jax = run(validator, submission("hk2", "mlp", width=16, depth=1, steps=32))
    assert jax["state"] == "SCORED"
    jax_state = validator.store.model_state(jax["submission_id"])["state"]
    assert worker.state_backend(jax_state) == "jax"

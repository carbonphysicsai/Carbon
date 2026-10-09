"""The battery validator scoring on a GPU (VALIDATOR-27: slice 1, JAX;
slice 2, PyTorch on the PyTorch GPU worker).

A GPU deployment scores on the host's recorded device under the validator
reconstruction role, only for a device class a hardware acceptance has
passed. The registry is empty until the A40 acceptance passes, so every GPU
deployment refuses today; the tests enter a class for their own duration
only. No GPU, container or chain: the device record is a fixture
observation and the carrier never dispatches.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_gpu_practice import device, gpu_image

from carbon.battery import deployment, rebuild_identity, worker
from carbon.development_session import research_carrier
from carbon.reconstruction import hardware_acceptance as ha
from carbon.reconstruction import torch_profile
from carbon.reconstruction.accelerators import GPU_PROFILE


@pytest.fixture
def record(monkeypatch):
    found = device()
    monkeypatch.setattr(research_carrier, "_gpu_device", lambda: found)
    return found


def accept(monkeypatch, kind, *profiles):
    """Enter `kind` for this test only, under JAX's profile by default."""
    entry = {"record": "TEST", "evidence": "TEST"}
    profiles = profiles or (GPU_PROFILE.profile_id,)
    monkeypatch.setitem(
        ha.ACCEPTED_DEVICE_CLASSES, kind, {profile: entry for profile in profiles}
    )


def torch_gpu_image():
    """The PyTorch GPU worker's identity: its own exact-hashed cu130 lock."""
    return gpu_image("8", lock=torch_profile.GPU_LOCK_DIGEST)


def test_only_an_accepted_device_class_scores(record, monkeypatch):
    # OWNER-GPU-DEVICE-CLASSES-01: the A40 and the RTX 4090 (this fixture's
    # device), each for both frameworks; no other class.
    both = {GPU_PROFILE.profile_id, torch_profile.GPU_PROFILE_ID}
    assert {k: set(v) for k, v in ha.ACCEPTED_DEVICE_CLASSES.items()} == {
        "NVIDIA A40": both,
        "NVIDIA GeForce RTX 4090": both,
    }
    assert record.device_kind == "NVIDIA GeForce RTX 4090"
    worker.CarrierBackend(SimpleNamespace(), gpu_image(), device="gpu")
    # A class no record names is refused.
    monkeypatch.setattr(ha, "ACCEPTED_DEVICE_CLASSES", {})
    with pytest.raises(ha.DeviceClassNotAccepted):
        worker.CarrierBackend(SimpleNamespace(), gpu_image(), device="gpu")


def test_an_accepted_class_labels_every_score_with_its_device(record, monkeypatch):
    accept(monkeypatch, record.device_kind)
    seen = {}

    def runner(ledger, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop before dispatch")

    backend = worker.CarrierBackend(
        SimpleNamespace(), gpu_image(), device="gpu", runner=runner
    )
    assert backend.identity["device_kind"] == record.device_kind
    assert backend.identity["device_record"] == record.digest
    reconstruction = {**backend.identity, "fit": {"backend": "jax"}}
    found = rebuild_identity.from_reconstruction(reconstruction)
    assert found["device_class"] == "gpu:" + record.device_kind
    with pytest.raises(worker.WorkerFailure):
        backend._call("op", "print(1)", {}, [], "jax")
    assert seen["accelerator"] == research_carrier.VALIDATOR_GPU
    assert seen["provenance"] == research_carrier.VALIDATOR_PROVENANCE


def test_a_cpu_deployment_is_exactly_what_it_was():
    seen = {}

    def runner(ledger, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop before dispatch")

    backend = worker.CarrierBackend(SimpleNamespace(), gpu_image(), runner=runner)
    assert "device_kind" not in backend.identity
    with pytest.raises(worker.WorkerFailure):
        backend._call("op", "print(1)", {}, [], "jax")
    assert "accelerator" not in seen


def test_pytorch_on_the_gpu_is_the_pytorch_gpu_worker_only(record, monkeypatch):
    accept(monkeypatch, record.device_kind)
    # The CPU PyTorch worker never runs on the validator's GPU.
    with pytest.raises(ValueError, match="GPU worker"):
        worker.CarrierBackend(
            SimpleNamespace(), gpu_image(), torch_image=gpu_image("7"), device="gpu"
        )


def test_pytorch_needs_its_own_acceptance_on_the_class(record, monkeypatch):
    accept(monkeypatch, record.device_kind)  # JAX only
    with pytest.raises(ha.DeviceClassNotAccepted):
        worker.CarrierBackend(
            SimpleNamespace(), gpu_image(), torch_image=torch_gpu_image(), device="gpu"
        )
    accept(
        monkeypatch, record.device_kind, torch_profile.GPU_PROFILE_ID
    )  # PyTorch only
    with pytest.raises(ha.DeviceClassNotAccepted):
        worker.CarrierBackend(
            SimpleNamespace(), gpu_image(), torch_image=torch_gpu_image(), device="gpu"
        )
    accept(
        monkeypatch,
        record.device_kind,
        GPU_PROFILE.profile_id,
        torch_profile.GPU_PROFILE_ID,
    )
    seen = {}

    def runner(ledger, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop before dispatch")

    backend = worker.CarrierBackend(
        SimpleNamespace(),
        gpu_image(),
        torch_image=torch_gpu_image(),
        device="gpu",
        runner=runner,
    )
    assert backend.backends == ("jax", "pytorch")
    assert backend.identity["pytorch_image"] == torch_gpu_image().image_id
    assert backend.identity["device_kind"] == record.device_kind
    with pytest.raises(worker.WorkerFailure):
        backend._call("op", "print(1)", {}, [], "pytorch")
    assert seen["image"] == torch_gpu_image()
    assert seen["accelerator"] == research_carrier.VALIDATOR_GPU


class Stop(Exception):
    pass


def test_the_carrier_runs_the_validator_role_on_an_accepted_class_only(
    record, monkeypatch, tmp_path
):
    requests = []

    def reserve(identity, **kwargs):
        requests.append(kwargs["request"])
        raise Stop

    ledger = SimpleNamespace(root=tmp_path, reserve=reserve)
    call = {
        "owner": "o",
        "identity": "t",
        "source": "print(1)",
        "files": {},
        "image": SimpleNamespace(image_id=gpu_image().image_id),
        "seconds": 60,
        "provenance": research_carrier.VALIDATOR_PROVENANCE,
        "extra_resources": {},
    }
    # Not accepted: refused before any reservation.
    monkeypatch.setattr(ha, "ACCEPTED_DEVICE_CLASSES", {})
    with pytest.raises(ha.DeviceClassNotAccepted):
        research_carrier._run_locked(
            ledger, accelerator=research_carrier.VALIDATOR_GPU, **call
        )
    assert requests == []
    accept(monkeypatch, record.device_kind)
    with pytest.raises(Stop):
        research_carrier._run_locked(
            ledger, accelerator=research_carrier.VALIDATOR_GPU, **call
        )
    assert requests[-1]["accelerator"] == {
        "kind": research_carrier.VALIDATOR_GPU,
        "profile": GPU_PROFILE.profile_id,
        "device": record.digest,
    }
    # The validator GPU is the validator's alone, and the validator's rebuild
    # never takes the miner lane's GPU.
    for provenance, accelerator in (
        ("BATTERY_PUBLIC_PRACTICE", research_carrier.VALIDATOR_GPU),
        (research_carrier.VALIDATOR_PROVENANCE, research_carrier.MINER_GPU),
    ):
        with pytest.raises(ValueError, match="unsupported accelerator"):
            research_carrier._run_locked(
                ledger, accelerator=accelerator, **{**call, "provenance": provenance}
            )


def test_the_validator_worker_profile_carries_the_pinned_determinism(
    record, monkeypatch, tmp_path
):
    from carbon.reconstruction.worker import accelerator_runtime, docker_runtime

    profile = research_carrier._worker_profile(
        record, research_carrier.VALIDATOR_PROVENANCE
    )
    assert profile.accelerator_role == "VALIDATOR_RECONSTRUCTION"
    assert profile.accelerator_grant_digest == record.digest
    miner = research_carrier._worker_profile(record, "BATTERY_PUBLIC_PRACTICE")
    assert miner.accelerator_role == "MINER_RESEARCH"
    monkeypatch.setattr(accelerator_runtime, "host_device", lambda: record)
    stage = tmp_path / "input"
    stage.mkdir()
    arguments = docker_runtime.create_arguments(
        container_name="carbon-v27-fixture",
        image_id=gpu_image().image_id,
        input_directory=stage,
        cpuset="0,1",
        launch_digest="sha256:" + "e" * 64,
        worker_profile=profile,
    )
    text = " ".join(arguments)
    assert "--gpus" in arguments
    assert "--xla_gpu_deterministic_ops=true" in text
    assert "CUBLAS_WORKSPACE_CONFIG=:4096:8" in text
    assert "NVIDIA_TF32_OVERRIDE=0" in text


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"device": "tpu"}, "evaluation_config_device"),
        ({"device": "gpu", "backend": "direct"}, "evaluation_config_device"),
    ],
)
def test_a_gpu_deployment_is_a_carrier(tmp_path, fields, code):
    import json

    config = {
        "schema": deployment.SCHEMA,
        "state": str(tmp_path / "s.sqlite3"),
        "private_root": str(tmp_path / "root.bin"),
        "journal": str(tmp_path / "j.jsonl"),
        "work": str(tmp_path / "work"),
        "backend": "carrier",
        "image_manifest": "/x/image.json",
        **fields,
    }
    path = tmp_path / "deployment.json"
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.load_config(path)
    assert refused.value.code == code


def test_the_pytorch_gpu_run_binds_and_checks_its_own_pins(
    record, monkeypatch, tmp_path
):
    requests = []

    def reserve(identity, **kwargs):
        requests.append(kwargs["request"])
        raise Stop

    ledger = SimpleNamespace(root=tmp_path, reserve=reserve)
    call = {
        "owner": "o",
        "identity": "t",
        "source": "print(1)",
        "files": {},
        "image": torch_gpu_image(),
        "seconds": 60,
        "provenance": research_carrier.VALIDATOR_PROVENANCE,
        "extra_resources": {},
    }
    accept(monkeypatch, record.device_kind)  # JAX's acceptance admits no PyTorch
    with pytest.raises(ha.DeviceClassNotAccepted):
        research_carrier._run_locked(
            ledger, accelerator=research_carrier.VALIDATOR_GPU, **call
        )
    accept(monkeypatch, record.device_kind, torch_profile.GPU_PROFILE_ID)
    with pytest.raises(Stop):
        research_carrier._run_locked(
            ledger, accelerator=research_carrier.VALIDATOR_GPU, **call
        )
    assert requests[-1]["accelerator"]["profile"] == torch_profile.GPU_PROFILE_ID
    # The miner lane's GPU never takes the PyTorch GPU worker's pins.
    assert research_carrier._gpu_pins(
        torch_gpu_image(), research_carrier.MINER_GPU
    ) == (
        GPU_PROFILE.profile_id,
        GPU_PROFILE.digest,
        GPU_PROFILE.environment_lock_digest,
    )


class Labels:
    """A Docker CLI that answers with the NVIDIA runtime and fixed labels."""

    def __init__(self, profile, environment):
        self.labels = {
            "org.opencontainers.image.carbon.accelerator.profile": profile,
            "org.opencontainers.image.carbon.accelerator.environment": environment,
        }

    def json(self, command):
        if command[0] == "info":
            return {"Runtimes": {"nvidia": {}}}
        return {"Config": {"Labels": self.labels}}


def test_the_pytorch_gpu_worker_is_checked_by_its_own_labels():
    from carbon.reconstruction.worker import accelerator_runtime
    from carbon.reconstruction.worker.model import WorkerFailure

    pins = research_carrier._gpu_pins(torch_gpu_image(), research_carrier.VALIDATOR_GPU)
    _, profile, lock = pins
    good = Labels(profile, lock)
    accelerator_runtime.verify_image_and_toolkit(
        cli=good, image=torch_gpu_image(), profile_digest=profile, lock_digest=lock
    )
    # JAX's labels on the PyTorch lock, or the PyTorch image checked as JAX's,
    # are refused.
    with pytest.raises(WorkerFailure):
        accelerator_runtime.verify_image_and_toolkit(
            cli=Labels(GPU_PROFILE.digest, lock),
            image=torch_gpu_image(),
            profile_digest=profile,
            lock_digest=lock,
        )
    with pytest.raises(WorkerFailure):
        accelerator_runtime.verify_image_and_toolkit(cli=good, image=torch_gpu_image())


def test_a_gpu_deployment_may_name_the_pytorch_gpu_worker(tmp_path):
    import json

    config = {
        "schema": deployment.SCHEMA,
        "state": str(tmp_path / "s.sqlite3"),
        "private_root": str(tmp_path / "root.bin"),
        "journal": str(tmp_path / "j.jsonl"),
        "work": str(tmp_path / "work"),
        "backend": "carrier",
        "image_manifest": "/x/image.json",
        "torch_image_manifest": "/x/torch-gpu.json",
        "device": "gpu",
    }
    path = tmp_path / "deployment.json"
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    assert deployment.load_config(path)["device"] == "gpu"

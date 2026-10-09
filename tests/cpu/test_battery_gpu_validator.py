"""The battery validator scoring on a GPU (VALIDATOR-27, slice 1: JAX).

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
from carbon.reconstruction.accelerators import GPU_PROFILE


@pytest.fixture
def record(monkeypatch):
    found = device()
    monkeypatch.setattr(research_carrier, "_gpu_device", lambda: found)
    return found


def accept(monkeypatch, kind):
    monkeypatch.setitem(
        ha.ACCEPTED_DEVICE_CLASSES,
        kind,
        {"profile_id": GPU_PROFILE.profile_id, "record": "TEST", "evidence": "TEST"},
    )


def test_no_device_class_is_accepted_until_a_hardware_acceptance_passes(record):
    assert ha.ACCEPTED_DEVICE_CLASSES == {}
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


def test_a_gpu_validator_serves_jax_only(record, monkeypatch):
    accept(monkeypatch, record.device_kind)
    with pytest.raises(ValueError, match="JAX only"):
        worker.CarrierBackend(
            SimpleNamespace(), gpu_image(), torch_image=gpu_image("8"), device="gpu"
        )


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
        (
            {"device": "gpu", "torch_image_manifest": "/x/torch.json"},
            "evaluation_config_device",
        ),
    ],
)
def test_a_gpu_deployment_is_a_jax_carrier(tmp_path, fields, code):
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

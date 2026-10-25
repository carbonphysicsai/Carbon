"""The miner lane's host record at launch (GPU_ANY_HOST_20261025.md step 2c;
Validator ruling 2026-10-25): a miner run accepts the miner record; every
validator, official and owner-authorised path refuses it; the live check
compares the identity and every field the record knows, and an `unknown`
field never matches a different GPU silently."""

from dataclasses import replace

import pytest
from test_gpu_self_service_controls import controls
from test_gpu_self_service_controls import self_service as _self_service

from carbon.reconstruction import accelerators, onboarding
from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
from carbon.reconstruction.host_inventory import (
    MinerHostDeviceRecord,
    require_miner_host_device,
)
from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker import docker_runtime as docker
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure


def self_service(record, role=AcceleratorRole.MINER_RESEARCH):
    return replace(
        _self_service(record, role), accelerator_device_uuid=record.device_uuid
    )


OBSERVED = {
    "devices": [
        {
            "device_uuid": "GPU-00000a16-1111-2222-3333-000000000a16",
            "device_kind": "NVIDIA A16-4Q",
            "driver_version": "550.90.07",
            "driver_model": "N/A",
            "compute_capability": "[Not Supported]",
            "device_memory_mib": "4096",
            "display_active": "[N/A]",
        }
    ]
}


@pytest.fixture
def miner_host(tmp_path, monkeypatch):
    root = tmp_path / "host"
    monkeypatch.setattr(runtime, "HOST_ROOT", root)
    document = onboarding.build_host_record(
        observed=OBSERVED,
        record_id="this-machine",
        provider="own-machine",
        platform="LINUX_VIRTUAL_MACHINE",
        container_runtime="DOCKER_ENGINE",
        provenance="a test observation",
        miner_lane=True,
    )
    onboarding.install_record(root, document, name="host-device.json")
    return root, MinerHostDeviceRecord.load(root)


def test_only_the_miner_accessor_reads_a_miner_record(miner_host):
    _, record = miner_host
    with pytest.raises(WorkerFailure):
        runtime.host_device()
    assert runtime.miner_host_device().digest == record.digest


def test_a_miner_record_serves_a_miner_run_and_never_a_validator_run(miner_host):
    _, record = miner_host
    env = accelerators.worker_environment(
        GPU_PROFILE, AcceleratorRole.MINER_RESEARCH, host_device=record
    )
    assert env["CUDA_VISIBLE_DEVICES"] == record.device_uuid
    assert env["CARBON_ACCELERATOR_DEVICE_KIND"] == "NVIDIA A16-4Q"
    for role in AcceleratorRole:
        if role is AcceleratorRole.MINER_RESEARCH:
            continue
        with pytest.raises(ValueError):
            accelerators.worker_environment(GPU_PROFILE, role, host_device=record)


def test_a_nameless_gpu_cannot_bind_the_worker(miner_host):
    _, record = miner_host
    document = dict(record.document)
    document["device_kind"] = "unknown"
    nameless = MinerHostDeviceRecord(document, record.digest)
    with pytest.raises(ValueError):
        accelerators.worker_environment(
            GPU_PROFILE, AcceleratorRole.MINER_RESEARCH, host_device=nameless
        )


def test_the_live_check_compares_what_the_record_knows(miner_host, tmp_path):
    _, record = miner_host
    profile = self_service(record)
    probe = controls(tmp_path, record, profile)
    # What the GPU really says: the record knows these, so they must match.
    probe.identity[:] = [
        record.device_uuid,
        "NVIDIA A16-4Q",
        "550.90.07",
        "4096",
        "Disabled",
    ]
    _, evidence = docker.inspect_effective_controls(cli=probe.cli, **probe.options)
    observation = evidence["accelerator"]
    assert observation["host_record_digest"] == record.digest
    assert observation["unknown_record_fields"] == list(record.unknown_fields)
    assert observation["official_eligible"] is False
    # A known field that differs refuses.
    for index in (1, 2, 3):
        probe = controls(tmp_path, record, profile)
        probe.identity[:] = [
            record.device_uuid,
            "NVIDIA A16-4Q",
            "550.90.07",
            "4096",
            "Disabled",
        ]
        probe.identity[index] = "different"
        with pytest.raises(WorkerFailure) as caught:
            docker.inspect_effective_controls(cli=probe.cli, **probe.options)
        assert caught.value.code is WorkerCode.POLICY
    # So does another device.
    probe = controls(tmp_path, record, profile)
    probe.identity[0] = "GPU-ffffffff-1111-2222-3333-000000000a16"
    with pytest.raises(WorkerFailure):
        docker.inspect_effective_controls(cli=probe.cli, **probe.options)


def test_an_unknown_field_matches_whatever_the_gpu_reports_and_says_so(
    miner_host, tmp_path
):
    root, record = miner_host
    document = dict(record.document)
    document["driver_version"] = "unknown"
    document["device_memory_mib"] = "unknown"
    onboarding.install_record(root, document, name="host-device.json")
    record = require_miner_host_device(MinerHostDeviceRecord.load(root), GPU_PROFILE)
    probe = controls(tmp_path, record, self_service(record))
    probe.identity[:] = [
        record.device_uuid,
        "NVIDIA A16-4Q",
        "999.1",
        "81920",
        "Enabled",
    ]
    _, evidence = docker.inspect_effective_controls(cli=probe.cli, **probe.options)
    assert {"driver_version", "device_memory_mib"} <= set(
        evidence["accelerator"]["unknown_record_fields"]
    )


def test_a_validator_self_service_run_refuses_the_miner_record(miner_host, tmp_path):
    _, record = miner_host
    profile = self_service(record, AcceleratorRole.VALIDATOR_RECONSTRUCTION)
    # The launch's own arguments already refuse it ...
    with pytest.raises(WorkerFailure):
        controls(tmp_path, record, profile)
    # ... and so does the live observation.
    miner = controls(tmp_path, record, self_service(record))
    with pytest.raises(WorkerFailure):
        runtime.inspect_self_service_device(
            cli=miner.cli, container_name="fixture", worker_profile=profile
        )


def test_the_strict_grant_paths_never_read_a_miner_record(miner_host):
    # The admission and approval documents bind to `host_device()`, the strict
    # record, so a miner record can never stand in for a grant.
    with pytest.raises(WorkerFailure):
        runtime.host_device()

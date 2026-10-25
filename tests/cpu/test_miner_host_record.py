"""The miner lane's host record (GPU_ANY_HOST_20261025.md step 2b; Validator
ruling 2026-10-25, question 1): a GPU whose vendor tool prints `[N/A]` or
`[Not Supported]` for a descriptive field gets a `carbon.host-device.miner.v1`
record with that field `unknown`, instead of a refusal.

The record is structurally separate from the strict one: every strict loader
(validator, official, owner-authorised) refuses it, and nothing converts one
into the other. The device identity is always known."""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import carbon_accelerator

from carbon.reconstruction import onboarding
from carbon.reconstruction.accelerators import GPU_PROFILE
from carbon.reconstruction.host_inventory import (
    MINER_DEVICE_SCHEMA,
    HostDeviceRecord,
    HostRecordRefused,
    MinerHostDeviceRecord,
    load_miner_lane_record,
    require_host_device,
    require_miner_host_device,
)
from carbon.reconstruction.worker.model import WorkerFailure

FIXTURES = ROOT / "tests" / "fixtures" / "gpu_hosts"
posix = pytest.mark.skipif(os.name == "nt", reason="a fake vendor tool needs POSIX")
VGPU = "vgpu-unsupported-fields-docker28"
GOOD = "rtx4090x1-wsl2-docker28"


def _observed(host):
    rows = (FIXTURES / host / "nvidia-smi-query.csv").read_text().splitlines()
    devices = []
    for row in rows:
        fields = [f.strip() for f in row.split(",")]
        devices.append(
            {
                "device_uuid": fields[0],
                "device_kind": ",".join(fields[1:-5]),
                "driver_version": fields[-5],
                "driver_model": onboarding._driver_model(fields[-4]),
                "compute_capability": fields[-3],
                "device_memory_mib": fields[-2],
                "display_active": fields[-1].capitalize(),
            }
        )
    return {"devices": devices, "source": "test"}


def _build(host, **extra):
    return onboarding.build_host_record(
        observed=_observed(host),
        record_id="this-machine",
        provider="own-machine",
        platform="LINUX_VIRTUAL_MACHINE",
        container_runtime="DOCKER_ENGINE",
        provenance="a test observation",
        now=1_700_000_000.0,
        **extra,
    )


def test_unreadable_descriptive_fields_become_unknown_on_the_miner_lane():
    document = _build(VGPU, miner_lane=True)
    assert document["schema"] == MINER_DEVICE_SCHEMA
    record = MinerHostDeviceRecord(document, "sha256:" + "0" * 64)
    assert record.problems() == ()
    assert set(record.unknown_fields) == {"compute_capability", "display_active"}
    assert document["device_uuid"] == "GPU-00000a16-1111-2222-3333-000000000a16"
    assert document["device_kind"] == "NVIDIA A16-4Q"
    assert require_miner_host_device(record, GPU_PROFILE) is record


def test_a_host_whose_fields_all_read_still_gets_the_strict_record():
    document = _build(GOOD, miner_lane=True)
    assert document["schema"] != MINER_DEVICE_SCHEMA
    HostDeviceRecord(document, "sha256:" + "0" * 64).validate()


def test_the_strict_path_still_refuses_unknown_fields():
    with pytest.raises(HostRecordRefused) as refused:
        _build(VGPU)
    assert "compute_capability" in refused.value.fields


def test_the_device_identity_must_be_sound_even_on_the_miner_lane():
    observed = _observed(VGPU)
    observed["devices"][0]["device_uuid"] = "GPU-1; rm -rf /"
    with pytest.raises(HostRecordRefused) as refused:
        onboarding.build_host_record(
            observed=observed,
            record_id="this-machine",
            provider="own-machine",
            platform="LINUX_VIRTUAL_MACHINE",
            container_runtime="DOCKER_ENGINE",
            provenance="a test observation",
            miner_lane=True,
        )
    assert refused.value.fields == ("device_uuid",)


def test_an_unreadable_memory_figure_is_unknown_not_a_crash():
    observed = _observed(VGPU)
    observed["devices"][0]["device_memory_mib"] = "[N/A]"
    document = onboarding.build_host_record(
        observed=observed,
        record_id="this-machine",
        provider="own-machine",
        platform="LINUX_VIRTUAL_MACHINE",
        container_runtime="DOCKER_ENGINE",
        provenance="a test observation",
        miner_lane=True,
    )
    record = MinerHostDeviceRecord(document, "sha256:" + "0" * 64)
    assert record.problems() == ()
    assert record.device_memory_mib is None
    assert "device_memory_mib" in record.unknown_fields


@pytest.mark.parametrize(
    "field,value",
    [
        ("device_kind", "x;rm -rf /"),
        ("driver_version", "550 && reboot"),
        ("driver_model", "ROCKET"),
        ("platform", "MY_BOX"),
        ("display_active", "maybe"),
    ],
)
def test_a_descriptive_field_is_unknown_or_valid_never_free_text(field, value):
    document = dict(_build(VGPU, miner_lane=True))
    document[field] = value
    record = MinerHostDeviceRecord(document, "sha256:" + "0" * 64)
    assert field in record.problems()


def _install(tmp_path, host):
    root = tmp_path / "root"
    onboarding.install_record(
        root, _build(host, miner_lane=True), name="host-device.json"
    )
    return root


def test_every_strict_loader_refuses_a_miner_record(tmp_path, monkeypatch):
    root = _install(tmp_path, VGPU)
    with pytest.raises(WorkerFailure):
        HostDeviceRecord.load(root)
    # The record the launch path reads from the host root.
    from carbon.reconstruction.worker import accelerator_runtime

    monkeypatch.setattr(accelerator_runtime, "HOST_ROOT", root)
    with pytest.raises(WorkerFailure):
        accelerator_runtime.host_device()
    # A miner record is not a strict record, whatever a caller passes.
    record = MinerHostDeviceRecord.load(root)
    with pytest.raises(WorkerFailure):
        require_host_device(record, GPU_PROFILE)
    # And the miner loader reads only the miner schema.
    strict_root = tmp_path / "strict"
    onboarding.install_record(
        strict_root, _build(GOOD, miner_lane=True), name="host-device.json"
    )
    with pytest.raises(WorkerFailure):
        MinerHostDeviceRecord.load(strict_root)
    assert type(load_miner_lane_record(root)) is MinerHostDeviceRecord
    assert type(load_miner_lane_record(strict_root)) is HostDeviceRecord


class _Docker:
    def json(self, arguments, **_):
        info = json.loads((FIXTURES / VGPU / "docker-info.json").read_text())
        return {"Version": info["ServerVersion"]} if arguments[0] == "version" else info


def test_doctor_is_ready_for_the_miner_lane_and_not_for_the_strict_one(tmp_path):
    root = _install(tmp_path, VGPU)
    report = onboarding.doctor_report(root=root, cli=_Docker())
    findings = {f["check"]: f for f in report["findings"]}
    assert findings["host_device_record"]["state"] == onboarding.READY
    assert findings["host_device_record"]["lane"] == "MINER"
    assert set(findings["host_device_record"]["unknown_fields"]) == {
        "compute_capability",
        "display_active",
    }
    assert findings["host_device_record_strict"]["state"] == onboarding.BLOCKED
    assert "host_device_record" not in report["miner_lane_blockers"]
    assert "host_device_record_strict" not in report["miner_lane_blockers"]
    assert report["checks_passed"] is False


def test_a_comma_in_the_marketed_name_is_read():
    class Run:
        returncode = 0
        stdout = (
            b"GPU-00000a16-1111-2222-3333-000000000a16, NVIDIA RTX, Pro 4000, "
            b"550.90.07, [N/A], 8.9, 20475, Disabled\n"
        )

    import subprocess

    original = subprocess.run
    subprocess.run = lambda *a, **k: Run()
    try:
        tool = ROOT / "tests" / "fixtures" / "gpu_hosts" / GOOD / "meta.json"
        observed = onboarding.observe_local_device(binary=str(tool))
    finally:
        subprocess.run = original
    device = observed["devices"][0]
    assert device["device_kind"] == "NVIDIA RTX, Pro 4000"
    assert device["compute_capability"] == "8.9"
    assert device["display_active"] == "Disabled"


@posix
def test_prepare_installs_the_miner_record_and_inspect_shows_it(tmp_path, capsys):
    tool = tmp_path / "nvidia-smi"
    tool.write_text(
        "#!/bin/sh\ncat <<'EOF'\n"
        + (FIXTURES / VGPU / "nvidia-smi-query.csv").read_text()
        + "EOF\n"
    )
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    root = tmp_path / "root"
    args = [
        "--host-root",
        str(root),
        "prepare",
        "--record-id",
        "this-machine",
        "--provider",
        "own-machine",
        "--platform",
        "LINUX_VIRTUAL_MACHINE",
        "--container-runtime",
        "DOCKER_ENGINE",
        "--miner-lane",
        "--smi",
        str(tool),
    ]
    assert carbon_accelerator.main(args) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "INSTALLED" and out["lane"] == "MINER"
    assert set(out["unknown_fields"]) == {"compute_capability", "display_active"}
    assert carbon_accelerator.main(["--host-root", str(root), "inspect"]) == 0
    shown = json.loads(capsys.readouterr().out)["host_device_record"]
    assert shown["schema"] == MINER_DEVICE_SCHEMA
    # Without --miner-lane the same machine is refused, naming the field.
    other = tmp_path / "other"
    refused = carbon_accelerator.main(
        [*args[:1], str(other), *args[2:-3], "--smi", str(tool)]
    )
    assert refused == 2
    assert "compute_capability" in json.loads(capsys.readouterr().out)["fields"]

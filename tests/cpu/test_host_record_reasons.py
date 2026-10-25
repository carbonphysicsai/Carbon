"""A refused host record names the failing fields, never their values.

The operator's `prepare` used to answer a record that failed its own shape with
only `reconstruction.worker.policy.mismatch`: no field, no next step. The refusal
now lists the failing field names with what each must be, while every caller that
catches `WorkerFailure` still sees the same stable policy failure. The vendor
tool's `[N/A]` (a field that does not apply, such as the Linux driver model) is
the record's "N/A"."""

import json
import os
import stat
import sys
from pathlib import Path

import accelerator_host
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import carbon_accelerator

from carbon.reconstruction import onboarding
from carbon.reconstruction.accelerators import GPU_PROFILE
from carbon.reconstruction.host_inventory import (
    HostDeviceRecord,
    HostRecordRefused,
)
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

SHAPE = min(accelerator_host.NVIDIA_SHAPES)
OBSERVED_DEVICE = {
    "device_uuid": "GPU-0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
    "device_kind": "NVIDIA RTX A6000",
    "driver_version": "580.126.09",
    "driver_model": "N/A",
    "compute_capability": "8.6",
    "device_memory_mib": "49140",
    "display_active": "Disabled",
}


def _record(**changes):
    document = dict(accelerator_host.document(SHAPE))
    document.update(changes)
    return HostDeviceRecord(document, "sha256:" + "0" * 64)


def _prepare(observed_device, **kwargs):
    return onboarding.build_host_record(
        observed={"devices": [observed_device]},
        device_uuid=None,
        profile=GPU_PROFILE,
        record_id="this-machine",
        provider="own-machine",
        platform=kwargs.get("platform", "HOSTED_COMPUTE_INSTANCE"),
        container_runtime="DOCKER_ENGINE",
        provenance="recorded observation from a test file",
    )


def test_a_well_formed_record_has_no_problems():
    assert _record().problems() == ()
    _record().validate()


@pytest.mark.parametrize(
    ("changes", "fields"),
    [
        ({"driver_model": "[N/A]"}, ("driver_model",)),
        ({"display_active": "[n/a]"}, ("display_active",)),
        ({"platform": "BARE"}, ("platform",)),
        ({"container_runtime": "PODMAN"}, ("container_runtime",)),
        ({"compute_capability": "eight"}, ("compute_capability",)),
        ({"device_memory_mib": 0}, ("device_memory_mib",)),
        ({"observed_at_unix": float("nan")}, ("observed_at_unix",)),
        (
            {"driver_model": "x", "display_active": "y"},
            ("driver_model", "display_active"),
        ),
    ],
)
def test_the_failing_fields_are_named_in_a_fixed_order(changes, fields):
    record = _record(**changes)
    assert record.problems() == fields
    with pytest.raises(WorkerFailure) as refused:
        record.validate()
    assert refused.value.code is WorkerCode.POLICY


def test_a_document_that_is_not_a_record_names_record():
    assert HostDeviceRecord({"nope": 1}, "sha256:" + "0" * 64).problems() == ("record",)
    assert HostDeviceRecord([], "sha256:" + "0" * 64).problems() == ("record",)


def test_prepare_refuses_by_naming_fields_and_still_a_policy_failure():
    with pytest.raises(HostRecordRefused) as refused:
        _prepare({**OBSERVED_DEVICE, "display_active": "[N/A]"})
    assert refused.value.fields == ("display_active",)
    assert isinstance(refused.value, WorkerFailure)
    assert refused.value.code is WorkerCode.POLICY


def test_a_bracketed_not_applicable_driver_model_is_the_records_na():
    assert onboarding._driver_model("[N/A]") == "N/A"
    assert onboarding._driver_model("") == "N/A"
    assert onboarding._driver_model("WDDM") == "WDDM"
    document = _prepare({**OBSERVED_DEVICE, "driver_model": "N/A"})
    assert document["driver_model"] == "N/A"


@pytest.mark.skipif(os.name == "nt", reason="a fake vendor tool needs POSIX")
def test_the_vendor_tool_s_bracketed_marker_reaches_the_record_as_na(tmp_path):
    smi = tmp_path / "nvidia-smi"
    smi.write_text(
        "#!/bin/sh\n"
        "echo 'GPU-0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0, NVIDIA RTX A6000, "
        "580.126.09, [N/A], 8.6, 49140, Disabled'\n"
    )
    smi.chmod(smi.stat().st_mode | stat.S_IXUSR)
    observed = onboarding.observe_local_device(binary=str(smi))
    assert observed["devices"][0]["driver_model"] == "N/A"
    document = onboarding.build_host_record(
        observed=observed,
        device_uuid=None,
        profile=GPU_PROFILE,
        record_id="this-machine",
        provider="own-machine",
        platform="HOSTED_COMPUTE_INSTANCE",
        container_runtime="DOCKER_ENGINE",
        provenance="vendor query tool run by the operator",
    )
    assert HostDeviceRecord(document, "sha256:" + "0" * 64).problems() == ()


def test_the_command_line_answers_a_refusal_with_fields_reasons_and_a_next_step(
    tmp_path, capsys
):
    source = tmp_path / "observed.json"
    secret = "SECRET-DISPLAY-VALUE"
    source.write_text(
        json.dumps({"devices": [{**OBSERVED_DEVICE, "display_active": secret}]})
    )
    code = carbon_accelerator.main(
        [
            "--host-root",
            str(tmp_path / "root"),
            "prepare",
            "--record-id",
            "this-machine",
            "--provider",
            "own-machine",
            "--platform",
            "HOSTED_COMPUTE_INSTANCE",
            "--container-runtime",
            "DOCKER_ENGINE",
            "--from",
            str(source),
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert out["status"] == "REFUSED"
    assert out["code"] == "reconstruction.worker.policy.mismatch"
    assert out["fields"] == ["display_active"]
    assert "Enabled or Disabled" in out["reasons"]["display_active"]
    assert out["next"]
    assert secret not in json.dumps(out)


def test_every_record_field_has_a_hint():
    from carbon.reconstruction.host_inventory import REQUIRED_FIELDS

    assert set(carbon_accelerator.FIELD_HINTS) >= REQUIRED_FIELDS


def test_a_multi_device_host_names_the_choice_and_lists_the_devices():
    from carbon.reconstruction.host_inventory import DeviceChoiceRequired

    second = {
        **OBSERVED_DEVICE,
        "device_uuid": "GPU-1f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
    }
    observed = {"devices": [OBSERVED_DEVICE, second]}
    with pytest.raises(DeviceChoiceRequired) as refused:
        onboarding.build_host_record(
            observed=observed,
            device_uuid=None,
            profile=GPU_PROFILE,
            record_id="this-machine",
            provider="own-machine",
            platform="LINUX_BARE_METAL",
            container_runtime="DOCKER_ENGINE",
            provenance="recorded observation from a test file",
        )
    assert refused.value.fields == ("device",)
    assert [c["device_uuid"] for c in refused.value.choices] == [
        OBSERVED_DEVICE["device_uuid"],
        second["device_uuid"],
    ]
    assert refused.value.code is WorkerCode.INVALID
    # Naming one of them works; naming one that is not there lists the choices again.
    document = onboarding.build_host_record(
        observed=observed,
        device_uuid=second["device_uuid"],
        profile=GPU_PROFILE,
        record_id="this-machine",
        provider="own-machine",
        platform="LINUX_BARE_METAL",
        container_runtime="DOCKER_ENGINE",
        provenance="recorded observation from a test file",
    )
    assert document["device_uuid"] == second["device_uuid"]
    with pytest.raises(DeviceChoiceRequired):
        onboarding.build_host_record(
            observed=observed,
            device_uuid="GPU-00000000-0000-0000-0000-000000000000",
            profile=GPU_PROFILE,
            record_id="this-machine",
            provider="own-machine",
            platform="LINUX_BARE_METAL",
            container_runtime="DOCKER_ENGINE",
            provenance="recorded observation from a test file",
        )


def test_the_command_line_lists_the_choices_for_a_multi_gpu_host(tmp_path, capsys):
    second = {
        **OBSERVED_DEVICE,
        "device_uuid": "GPU-1f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
    }
    source = tmp_path / "observed.json"
    source.write_text(json.dumps({"devices": [OBSERVED_DEVICE, second]}))
    code = carbon_accelerator.main(
        [
            "--host-root",
            str(tmp_path / "root"),
            "prepare",
            "--record-id",
            "this-machine",
            "--provider",
            "own-machine",
            "--platform",
            "LINUX_BARE_METAL",
            "--container-runtime",
            "DOCKER_ENGINE",
            "--from",
            str(source),
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert out["code"] == "reconstruction.worker.request.invalid"
    assert out["fields"] == ["device"]
    assert "--device" in out["reasons"]["device"]
    assert [c["device_uuid"] for c in out["choices"]] == [
        OBSERVED_DEVICE["device_uuid"],
        second["device_uuid"],
    ]


def test_the_doctor_says_whether_your_own_practice_is_blocked():
    findings = [
        {"check": "installed_authority", "state": "BLOCKED"},
        {"check": "host_device_record", "state": "READY"},
    ]
    assert onboarding.miner_lane_blockers({"findings": findings}) == []
    findings.append({"check": "container_daemon", "state": "BLOCKED"})
    assert onboarding.miner_lane_blockers({"findings": findings}) == [
        "container_daemon"
    ]


def test_the_installer_says_how_to_get_what_is_missing():
    script = (ROOT / "scripts" / "install_miner.sh").read_text(encoding="utf-8")
    assert 'is not installed. $(install_hint "${tool}")' in script
    assert "https://docs.docker.com/engine/install/" in script
    assert "NVIDIA Container Toolkit" in script

"""Onboarding a host without editing Carbon.

Every host here is synthetic and every observation is a fixture. No device is
attached, no vendor tool is run against real hardware, nothing is dispatched and
no authority is created. These check that the *steps* are provider-independent
and that they refuse the things they must refuse - not that Carbon works on any
particular machine.
"""

import json

import accelerator_host
import pytest

from carbon.reconstruction import onboarding
from carbon.reconstruction.accelerators import GPU_PROFILE, TPU_PROFILE
from carbon.reconstruction.host_inventory import (
    HOST_DEVICE_RECORD,
    HostDeviceRecord,
    require_host_device,
)
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

# One observation per host shape, in the form the vendor tool reports. Synthetic
# values throughout; none of these is a claim that such a host works.
OBSERVATIONS = {
    name: {
        "source": "/usr/bin/nvidia-smi",
        "devices": [
            {
                "device_uuid": host["device_uuid"],
                "device_kind": host["device_kind"],
                "driver_version": host["driver_version"],
                "driver_model": host["driver_model"],
                "compute_capability": host["compute_capability"],
                "device_memory_mib": str(host["device_memory_mib"]),
                "display_active": host["display_active"],
            }
        ],
    }
    for name, host in accelerator_host.HOSTS.items()
}


@pytest.fixture
def root(tmp_path):
    return tmp_path / "host"


# --- the portability claim ----------------------------------------------------


@pytest.mark.parametrize("shape", sorted(accelerator_host.NVIDIA_SHAPES))
def test_any_host_shape_is_prepared_by_the_same_command(root, shape):
    """The whole point of §3: a different machine is a different record."""
    host = accelerator_host.HOSTS[shape]
    document = onboarding.build_host_record(
        observed=OBSERVATIONS[shape],
        record_id=host["record_id"],
        provider=host["provider"],
        platform=host["platform"],
        container_runtime=host["container_runtime"],
        provenance="synthetic fixture observation",
    )
    onboarding.install_record(root, document, name=HOST_DEVICE_RECORD)
    record = require_host_device(HostDeviceRecord.load(root), GPU_PROFILE)
    assert record.device_uuid == host["device_uuid"]
    assert record.provider == host["provider"]
    assert record.platform == host["platform"]
    assert record.container_runtime == host["container_runtime"]


def test_no_provider_or_platform_gets_special_treatment(root):
    """Same inputs, different provider and platform: same code path."""
    documents = []
    for platform in sorted(
        {"WSL2", "LINUX_BARE_METAL", "LINUX_VIRTUAL_MACHINE", "HOSTED_COMPUTE_INSTANCE"}
    ):
        for provider in ("self-hosted", "example-provider", "another-provider"):
            documents.append(
                onboarding.build_host_record(
                    observed=OBSERVATIONS["workstation_linux"],
                    record_id="host",
                    provider=provider,
                    platform=platform,
                    container_runtime="DOCKER_ENGINE",
                    provenance="synthetic fixture observation",
                    now=1000.0,
                )
            )
    # The documents differ only in the two fields that were varied.
    varied = {(document["platform"], document["provider"]) for document in documents}
    assert len(varied) == len(documents)
    for document in documents:
        rest = {
            key: value
            for key, value in document.items()
            if key not in {"platform", "provider"}
        }
        assert rest == {
            key: value
            for key, value in documents[0].items()
            if key not in {"platform", "provider"}
        }


def test_a_multi_device_host_requires_an_explicit_choice(root):
    """Carbon must not pick a device for the operator."""
    observed = {
        "source": "/usr/bin/nvidia-smi",
        "devices": [
            OBSERVATIONS["multi_device_host"]["devices"][0],
            {
                **OBSERVATIONS["multi_device_host"]["devices"][0],
                "device_uuid": "GPU-77777777-7777-7777-7777-777777777777",
            },
        ],
    }
    with pytest.raises(WorkerFailure) as error:
        onboarding.build_host_record(
            observed=observed,
            record_id="host",
            provider="example-provider",
            provenance="synthetic fixture observation",
        )
    assert error.value.code is WorkerCode.INVALID

    chosen = onboarding.build_host_record(
        observed=observed,
        device_uuid="GPU-77777777-7777-7777-7777-777777777777",
        record_id="host",
        provider="example-provider",
        platform="LINUX_VIRTUAL_MACHINE",
        container_runtime="DOCKER_ENGINE",
        provenance="synthetic fixture observation",
    )
    assert chosen["device_uuid"] == "GPU-77777777-7777-7777-7777-777777777777"

    with pytest.raises(WorkerFailure):
        onboarding.build_host_record(
            observed=observed,
            device_uuid="GPU-00000000-0000-0000-0000-000000000000",
            record_id="host",
            provider="example-provider",
            provenance="synthetic fixture observation",
        )


def test_an_incompatible_host_is_refused_before_anything_is_written(root):
    """A hostile or malformed observation never lands on disk."""
    for devices in (
        [{**OBSERVATIONS["laptop_wsl2"]["devices"][0], "device_uuid": "$(id)"}],
        [{**OBSERVATIONS["laptop_wsl2"]["devices"][0], "device_kind": "a\nb"}],
        [{**OBSERVATIONS["laptop_wsl2"]["devices"][0], "driver_model": "MYSTERY"}],
        [{**OBSERVATIONS["laptop_wsl2"]["devices"][0], "device_memory_mib": "lots"}],
        [{**OBSERVATIONS["laptop_wsl2"]["devices"][0], "compute_capability": "x"}],
        [],
    ):
        with pytest.raises(WorkerFailure):
            onboarding.build_host_record(
                observed={"devices": devices},
                record_id="host",
                provider="example-provider",
                provenance="synthetic fixture observation",
            )
    assert not (root / HOST_DEVICE_RECORD).exists()


def test_a_record_prepared_for_one_workload_will_not_serve_another(root):
    document = onboarding.build_host_record(
        observed=OBSERVATIONS["laptop_wsl2"],
        profile=GPU_PROFILE,
        record_id="host",
        provider="self-hosted",
        platform="WSL2",
        container_runtime="DOCKER_DESKTOP",
        provenance="synthetic fixture observation",
    )
    onboarding.install_record(root, document, name=HOST_DEVICE_RECORD)
    record = HostDeviceRecord.load(root)
    with pytest.raises(WorkerFailure):
        require_host_device(record, TPU_PROFILE)


# --- preparing describes, it does not authorize --------------------------------


def test_preparing_a_record_installs_no_authority(root):
    from carbon.reconstruction.worker.development_admission import DEVELOPMENT_RECORD

    document = onboarding.build_host_record(
        observed=OBSERVATIONS["laptop_wsl2"],
        record_id="host",
        provider="self-hosted",
        platform="WSL2",
        container_runtime="DOCKER_DESKTOP",
        provenance="synthetic fixture observation",
    )
    onboarding.install_record(root, document, name=HOST_DEVICE_RECORD)
    assert not (root / "grant.json").exists()
    assert not (root / DEVELOPMENT_RECORD).exists()
    assert document["observation_authority"] == (
        "HOST_OBSERVATION_ONLY_NOT_QUALIFICATION"
    )


def test_authorize_installs_only_a_recognised_authority_record(root):
    from carbon.reconstruction.worker import accelerator_runtime as runtime
    from carbon.reconstruction.worker.development_admission import (
        DEVELOPMENT_RECORD,
        DEVELOPMENT_SCHEMA,
    )

    path = onboarding.install_authority(root, {"schema": runtime.GRANT_SCHEMA})
    assert path.name == "grant.json"
    path = onboarding.install_authority(root, {"schema": DEVELOPMENT_SCHEMA})
    assert path.name == DEVELOPMENT_RECORD

    for document in (
        {"schema": "carbon.accelerator-host-device.v1"},
        {"schema": "something-else"},
        {},
        "not-a-document",
    ):
        with pytest.raises(WorkerFailure):
            onboarding.install_authority(root, document)


def test_installed_records_are_operator_private(root):
    document = onboarding.build_host_record(
        observed=OBSERVATIONS["laptop_wsl2"],
        record_id="host",
        provider="self-hosted",
        platform="WSL2",
        container_runtime="DOCKER_DESKTOP",
        provenance="synthetic fixture observation",
    )
    path = onboarding.install_record(root, document, name=HOST_DEVICE_RECORD)
    assert path.stat().st_mode & 0o077 == 0
    assert root.stat().st_mode & 0o077 == 0


# --- the doctor reports blockers rather than hiding them -----------------------


class _CLI:
    """A bounded stand-in for the container CLI. No daemon is contacted."""

    def __init__(self, info=None, fail=False):
        self.info = info
        self.fail = fail

    def json(self, command):
        if self.fail:
            raise WorkerFailure(WorkerCode.UNAVAILABLE)
        if command[0] == "info":
            return self.info
        if command[0] == "version":
            return {"Version": "0.0.0"}
        return {}

    def run(self, *args, **kwargs):  # pragma: no cover - never reached
        raise AssertionError("doctor must not run containers")


def _by_check(report):
    return {finding["check"]: finding for finding in report["findings"]}


def test_doctor_reports_a_missing_record_rather_than_guessing(root):
    report = onboarding.doctor_report(root=root, cli=_CLI(info={}))
    findings = _by_check(report)
    assert findings["host_device_record"]["state"] == onboarding.BLOCKED
    assert "host_device_record" in report["blocked"]
    assert not report["checks_passed"]
    # And it never claims acceptance.
    assert report["authority"] == "HOST_READINESS_CHECKS_ONLY_NOT_ACCEPTANCE"


def test_doctor_names_the_container_runtime_and_says_unknown_when_it_cannot(root):
    engine = onboarding.doctor_report(
        root=root, cli=_CLI(info={"OperatingSystem": "Ubuntu 24.04", "Runtimes": {}})
    )
    assert _by_check(engine)["container_runtime"]["value"] == onboarding.DOCKER_ENGINE

    desktop = onboarding.doctor_report(
        root=root,
        cli=_CLI(info={"OperatingSystem": "Docker Desktop", "Runtimes": {}}),
    )
    assert _by_check(desktop)["container_runtime"]["value"] == onboarding.DOCKER_DESKTOP

    unknown = onboarding.doctor_report(root=root, cli=_CLI(fail=True))
    runtime_finding = _by_check(unknown)["container_runtime"]
    assert runtime_finding["value"] == onboarding.UNKNOWN
    assert runtime_finding["state"] == onboarding.UNKNOWN
    assert "container_runtime" in unknown["unknown"]


def test_doctor_reports_the_missing_device_runtime(root):
    without = onboarding.doctor_report(
        root=root, cli=_CLI(info={"OperatingSystem": "Ubuntu 24.04", "Runtimes": {}})
    )
    assert _by_check(without)["container_device_runtime"]["state"] == onboarding.BLOCKED
    with_device = onboarding.doctor_report(
        root=root,
        cli=_CLI(info={"OperatingSystem": "Ubuntu 24.04", "Runtimes": {"nvidia": {}}}),
    )
    assert (
        _by_check(with_device)["container_device_runtime"]["state"] == onboarding.READY
    )


def test_doctor_reports_unsupported_enumeration_on_a_wddm_host(root):
    accelerator_host.install(root, accelerator_host.document("laptop_wsl2"))
    report = onboarding.doctor_report(root=root, cli=_CLI(info={}))
    finding = _by_check(report)["compute_process_enumeration"]
    assert finding["state"] == onboarding.BLOCKED
    assert finding["value"] == "UNSUPPORTED"
    assert "compute_process_enumeration" in report["blocked"]


def test_doctor_reports_a_display_attached_device(root):
    accelerator_host.install(
        root, accelerator_host.document("workstation_linux", display_active="Enabled")
    )
    report = onboarding.doctor_report(root=root, cli=_CLI(info={}))
    assert _by_check(report)["display_output"]["state"] == onboarding.BLOCKED


def test_doctor_reports_quarantine_and_never_clears_it(root):
    accelerator_host.install(root)
    marker = root / "device-quarantined"
    marker.write_bytes(b"UNRECONCILED_DEVICE_RELEASE\n")
    report = onboarding.doctor_report(root=root, cli=_CLI(info={}))
    assert _by_check(report)["device_quarantine"]["state"] == onboarding.BLOCKED
    assert marker.is_file(), "doctor is read-only"


def test_doctor_reports_missing_authority(root):
    accelerator_host.install(root)
    report = onboarding.doctor_report(root=root, cli=_CLI(info={}))
    assert _by_check(report)["installed_authority"]["state"] == onboarding.BLOCKED


def test_doctor_reports_an_unreconciled_attempt(root):
    from carbon.reconstruction.worker.development_admission import (
        DevelopmentAttemptJournal,
    )

    accelerator_host.install(root)
    DevelopmentAttemptJournal(root).reserve(
        nonce="a" * 32, plan_digest="sha256:" + "5" * 64, budget=4, now=1.0
    )
    report = onboarding.doctor_report(root=root, cli=_CLI(info={}))
    finding = _by_check(report)["attempt_accounting"]
    assert finding["state"] == onboarding.BLOCKED


def test_status_is_read_only_and_reports_consumption(root, tmp_path):
    from carbon.reconstruction.worker.development_admission import (
        DevelopmentAttemptJournal,
    )

    accelerator_host.install(root)
    journal = DevelopmentAttemptJournal(root)
    journal.reserve(nonce="a" * 32, plan_digest="sha256:" + "5" * 64, budget=4, now=1.0)
    journal.settle(nonce="a" * 32, state="COMPLETED")
    before = sorted(path.name for path in root.rglob("*"))
    report = onboarding.status_report(root=root, state_root=tmp_path / "controller")
    assert report["attempts_consumed"] == 1
    assert report["unreconciled_attempt"] is None
    assert report["device_quarantined"] is False
    assert sorted(path.name for path in root.rglob("*")) == before


# --- the command surface -------------------------------------------------------


def _cli_main(argv, capsys):
    import carbon_accelerator

    code = carbon_accelerator.main(argv)
    return code, json.loads(capsys.readouterr().out)


@pytest.fixture(autouse=True)
def importable_cli(monkeypatch):
    from pathlib import Path as _Path

    monkeypatch.syspath_prepend(
        str(_Path(__file__).resolve().parents[2] / "scripts" / "dev")
    )


def test_inspect_shows_the_profile_and_says_no_record_is_installed(root, capsys):
    code, value = _cli_main(["--host-root", str(root), "inspect"], capsys)
    assert code == 0
    assert value["host_device_record"] is None
    assert value["workload_profile"]["profile_id"] == GPU_PROFILE.profile_id
    assert "device_uuid" not in value["workload_profile"]


def test_prepare_then_inspect_round_trips_through_the_command(root, tmp_path, capsys):
    source = tmp_path / "observed.json"
    source.write_text(json.dumps(OBSERVATIONS["hosted_instance"]))
    code, value = _cli_main(
        [
            "--host-root",
            str(root),
            "prepare",
            "--record-id",
            "hosted-instance",
            "--provider",
            "example-provider",
            "--platform",
            "HOSTED_COMPUTE_INSTANCE",
            "--container-runtime",
            "DOCKER_ENGINE",
            "--from",
            str(source),
        ],
        capsys,
    )
    assert code == 0 and value["status"] == "INSTALLED"
    code, value = _cli_main(["--host-root", str(root), "inspect"], capsys)
    assert code == 0
    assert (
        value["host_device_record"]["device_uuid"]
        == accelerator_host.HOSTS["hosted_instance"]["device_uuid"]
    )


def test_prepare_dry_run_writes_nothing(root, tmp_path, capsys):
    source = tmp_path / "observed.json"
    source.write_text(json.dumps(OBSERVATIONS["workstation_linux"]))
    code, value = _cli_main(
        [
            "--host-root",
            str(root),
            "prepare",
            "--record-id",
            "workstation",
            "--provider",
            "self-hosted",
            "--platform",
            "LINUX_BARE_METAL",
            "--container-runtime",
            "DOCKER_ENGINE",
            "--from",
            str(source),
            "--dry-run",
        ],
        capsys,
    )
    assert code == 0 and value["status"] == "NOT_WRITTEN"
    assert not (root / HOST_DEVICE_RECORD).exists()


def test_the_command_refuses_a_malformed_record_id(root, tmp_path, capsys):
    source = tmp_path / "observed.json"
    source.write_text(json.dumps(OBSERVATIONS["workstation_linux"]))
    code, value = _cli_main(
        [
            "--host-root",
            str(root),
            "prepare",
            "--record-id",
            "not a token",
            "--provider",
            "self-hosted",
            "--from",
            str(source),
        ],
        capsys,
    )
    assert code == 2 and value["status"] == "REFUSED"
    assert not (root / HOST_DEVICE_RECORD).exists()


def test_doctor_exits_non_zero_while_blocked(root, capsys, monkeypatch):
    from carbon.reconstruction.worker import docker_runtime

    monkeypatch.setattr(
        docker_runtime, "DockerCLI", lambda *a, **k: _CLI(info={}), raising=True
    )
    code, value = _cli_main(["--host-root", str(root), "doctor"], capsys)
    assert code == 1
    assert value["blocked"]


def test_the_command_never_imports_a_numerical_backend():
    """Onboarding must not pull in or start JAX."""
    import subprocess
    import sys
    from pathlib import Path as _Path

    repository = _Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            str(repository / "scripts" / "dev" / "carbon_accelerator.py"),
            "--host-root",
            str(repository / "does-not-exist"),
            "inspect",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(repository),
        env={
            "PATH": "/usr/bin:/bin",
            "CARBON_ASSERT_NO_JAX": "1",
            "PYTHONPATH": str(repository),
        },
    )
    assert result.returncode == 0, result.stderr
    assert "device_uuid" not in json.loads(result.stdout)["workload_profile"]

"""Own-GPU `prepare` and `doctor` against fake host outputs, one test per shape of
host we have met ($0, no GPU, no Docker): each refusal prints the fields it
concerns and a next step, and a wallet-less newcomer is never asked for an
owner-supplied grant.

Shapes: a multi-GPU machine (4x RTX 4090), the vendor tool's "[N/A]" driver
model, no NVIDIA driver (and a driver that is not loaded), Docker missing or not
reachable, no NVIDIA container runtime, Docker buildx missing, Docker 28 vs 29
image ids, and a newcomer with no owner grant. The fakes stand in for nvidia-smi
and the Docker CLI; the record, the doctor and the command line are real."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from test_install_gpu_both_backends import sandbox  # noqa: F401 - fixture
from test_parent_image_fingerprint import TAG, Cli, _identity, _recorded

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import carbon_accelerator

from carbon.reconstruction import onboarding
from carbon.reconstruction.worker.docker_runtime import WorkerFailure
from carbon.reconstruction.worker.model import WorkerCode

posix = pytest.mark.skipif(os.name == "nt", reason="a fake vendor tool needs POSIX")
DOCKER_URL = "https://docs.docker.com/engine/install/"
TOOLKIT_URL = "https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/"
DRIVER_URL = "https://www.nvidia.com/en-us/drivers/"


def _smi(tmp_path, rows, *, exit_code=0):
    tool = tmp_path / "nvidia-smi"
    body = "\n".join(f"echo '{row}'" for row in rows)
    tool.write_text(f"#!/bin/sh\n{body}\nexit {exit_code}\n")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    return tool


def _row(index=0, driver_model="[N/A]", display="Disabled"):
    return (
        f"GPU-0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f{index}, NVIDIA GeForce RTX 4090, "
        f"580.178.04, {driver_model}, 8.9, 24564, {display}"
    )


def _prepare(tmp_path, capsys, *extra, smi=None):
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
            "--dry-run",
            *(["--smi", str(smi)] if smi else []),
            *extra,
        ]
    )
    return code, json.loads(capsys.readouterr().out)


# --- prepare ------------------------------------------------------------------


@posix
def test_a_four_gpu_machine_lists_its_gpus_and_asks_for_one(tmp_path, capsys):
    smi = _smi(tmp_path, [_row(i) for i in range(4)])
    code, out = _prepare(tmp_path, capsys, smi=smi)
    assert code == 2 and out["status"] == "REFUSED"
    assert out["fields"] == ["device"]
    assert "--device" in out["reasons"]["device"]
    assert len(out["choices"]) == 4
    assert "--device" in out["next"] or "report the field" in out["next"]
    # Naming one works.
    code, out = _prepare(
        tmp_path, capsys, "--device", out["choices"][2]["device_uuid"], smi=smi
    )
    assert code == 0 and out["status"] == "NOT_WRITTEN"
    assert out["document"]["device_uuid"].endswith("f2")


@posix
def test_the_vendor_tool_s_bracketed_na_driver_model_is_accepted(tmp_path, capsys):
    code, out = _prepare(tmp_path, capsys, smi=_smi(tmp_path, [_row()]))
    assert code == 0 and out["status"] == "NOT_WRITTEN"
    assert out["document"]["driver_model"] == "N/A"


@posix
def test_a_display_value_the_record_does_not_take_names_its_field(tmp_path, capsys):
    smi = _smi(tmp_path, [_row(display="[N/A]")])
    code, out = _prepare(tmp_path, capsys, smi=smi)
    assert code == 2 and out["fields"] == ["display_active"]
    assert "Enabled or Disabled" in out["reasons"]["display_active"]
    assert out["next"]


def test_no_nvidia_driver_says_how_to_get_one(tmp_path, capsys):
    code, out = _prepare(tmp_path, capsys, smi=tmp_path / "absent-nvidia-smi")
    assert code == 2 and out["status"] == "REFUSED"
    assert out["fields"] == ["nvidia_smi"]
    assert "nvidia-smi" in out["reasons"]["nvidia_smi"]
    assert DRIVER_URL in out["next"] and "--smi" in out["next"]


@posix
def test_a_driver_that_is_not_loaded_says_the_same(tmp_path, capsys):
    smi = _smi(tmp_path, [], exit_code=9)
    code, out = _prepare(tmp_path, capsys, smi=smi)
    assert code == 2 and out["fields"] == ["nvidia_smi"]
    assert DRIVER_URL in out["next"]


# --- doctor -------------------------------------------------------------------


class Host(Cli):
    """Docker 28 ("classic" store) or 29 ("containerd" store) with or without the
    NVIDIA runtime; `down` is a Docker that answers nothing."""

    def __init__(self, store="classic", *, nvidia=True, down=False, **kwargs):
        super().__init__(store, _identity(), **kwargs)
        self.nvidia, self.down = nvidia, down
        self.info.update(
            {
                "OperatingSystem": "Ubuntu 24.04",
                "Runtimes": {"nvidia": {}, "runc": {}} if nvidia else {"runc": {}},
            }
        )

    def json(self, arguments, **kwargs):
        if self.down:
            raise WorkerFailure(WorkerCode.UNAVAILABLE)
        return super().json(arguments, **kwargs)

    def run(self, arguments, **kwargs):
        if self.down:
            raise WorkerFailure(WorkerCode.UNAVAILABLE)
        return super().run(arguments, **kwargs)


def _doctor(tmp_path, host):
    return onboarding.doctor_report(root=tmp_path / "root", cli=host, image=_identity())


def _finding(report, check):
    return next(f for f in report["findings"] if f["check"] == check)


def test_docker_missing_or_unreachable_says_how_to_install_it(tmp_path):
    report = _doctor(tmp_path, Host(down=True))
    daemon = _finding(report, "container_daemon")
    assert daemon["state"] == "BLOCKED"
    assert DOCKER_URL in daemon["next"]
    assert "container_daemon" in report["miner_lane_blockers"]
    assert not report["miner_lane_ready"]
    assert any(DOCKER_URL in step for step in report["miner_next"])


def test_no_nvidia_container_runtime_says_how_to_install_the_toolkit(tmp_path):
    report = _doctor(tmp_path, Host(nvidia=False))
    runtime = _finding(report, "container_device_runtime")
    assert runtime["state"] == "BLOCKED" and TOOLKIT_URL in runtime["next"]
    assert "container_device_runtime" in report["miner_lane_blockers"]


def test_docker_28_finds_the_image_by_its_id(tmp_path):
    report = _doctor(tmp_path, Host("classic"))
    assert _finding(report, "container_daemon")["state"] == "READY"


def test_docker_29_without_the_recorded_id_says_to_rebuild_it(tmp_path):
    report = _doctor(tmp_path, Host("containerd"))
    daemon = _finding(report, "container_daemon")
    assert daemon["state"] == "BLOCKED"
    assert "--update --gpu" in daemon["next"]
    assert TAG  # the fake store answers the tag, not the config digest
    assert _recorded()


def test_a_newcomer_without_an_owner_grant_is_not_blocked(
    tmp_path, monkeypatch, capsys
):
    report = _doctor(tmp_path, Host("classic"))
    authority = _finding(report, "installed_authority")
    assert authority["state"] == "BLOCKED"
    assert "not needed for your own practice" in authority["next"]
    assert "installed_authority" not in report["miner_lane_blockers"]
    # Only the missing host record stands between this newcomer and practice.
    assert report["miner_lane_blockers"] == ["host_device_record"]
    record = _finding(report, "host_device_record")
    assert "carbon_accelerator.py prepare" in record["next"]
    # With a record, the miner lane is ready though the grant is still absent.
    report["findings"] = [
        f for f in report["findings"] if f["check"] != "host_device_record"
    ]
    assert onboarding.miner_lane_blockers(report) == []
    # The bare command stays strict (a validator or owner-authorised host must pass
    # every check); the miner lane asks explicitly.
    ready = {
        "checks_passed": False,
        "miner_lane_ready": True,
        "findings": [],
    }
    monkeypatch.setattr(onboarding, "doctor_report", lambda **_: ready)
    for flag, expected in (([], 1), (["--miner-lane"], 0)):
        code = carbon_accelerator.main(
            ["--host-root", str(tmp_path / "root"), "doctor", *flag]
        )
        capsys.readouterr()
        assert code == expected


def test_every_blocked_or_unknown_finding_carries_a_next_step(tmp_path):
    for host in (Host(down=True), Host(nvidia=False), Host("containerd")):
        for finding in _doctor(tmp_path, host)["findings"]:
            if finding["state"] != "READY":
                assert finding["next"], finding


# --- installer ----------------------------------------------------------------


def _hint(tool):
    script = (ROOT / "scripts" / "install_miner.sh").read_text(encoding="utf-8")
    start = script.index("install_hint() {")
    end = script.index("\n}\n", start) + 3
    return subprocess.run(
        ["bash", "-c", f'{script[start:end]}\ninstall_hint "{tool}"'],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


@posix
def test_docker_not_installed_says_how_to_get_it():
    assert DOCKER_URL in _hint("docker")
    assert "apt-get install git" in _hint("git")


@posix
def test_docker_buildx_missing_says_how_to_get_it(sandbox):  # noqa: F811
    docker = sandbox.tools / "docker"
    docker.write_text(
        '#!/bin/sh\ncase "$1" in buildx) echo "docker: unknown command" >&2; exit 1 ;; esac\n'
        'if [ "$*" = "info --format {{.DockerRootDir}}" ]; then\n'
        '  echo "$CARBON_TEST_DOCKER_ROOT"\nfi\nexit 0\n'
    )
    docker.chmod(0o755)
    refused = sandbox.run("--pytorch", "--gpu", "--no-start")
    assert refused.returncode == 2
    assert "needs Docker buildx" in refused.stderr
    assert "docker-buildx-plugin" in refused.stderr
    assert "run the installer again" in refused.stderr

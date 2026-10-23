"""The compute check reads the miner's driver CUDA and warns (M1 S5).

On an A6000 pod whose driver runs CUDA 12.8, the PyTorch cu130 worker
practised on the GPU while the JAX cuda13 worker's build failed with
cudaErrorInsufficientDriver - after setup had read both as ready, and with
nothing shown to the miner. Now:
- the remote check reads the newest CUDA the driver runs (nvidia-smi only:
  it still starts nothing, OWNER-MINER-COMPUTE-LINK-ONLY-01), and setup warns
  in plain words when a worker is built for a newer CUDA - a warning, since a
  worker whose image carries CUDA's forward-compatibility libraries runs;
- a remote build that fails that way records `gpu_driver_too_old`, and the
  practice runs on CPU saying so.
Scripts run for real in bash against a fake docker and nvidia-smi.
"""

from __future__ import annotations

import os
import subprocess
from types import SimpleNamespace

import pytest

from carbon.compute import remote_runner
from carbon.compute.remote_job import RemoteJobFailure
from carbon.compute.remote_machine import (
    NO_NVIDIA_TOOLKIT,
    NO_WORKER_IMAGE,
    RemoteMachineError,
    check_script,
    driver_cuda,
)

IMAGE = "sha256:" + "a" * 64


def fake_host(tmp_path, probe_output, probe_rc):
    """A machine with Docker holding the worker, the NVIDIA toolkit, one GPU
    on a CUDA 12.8 driver, and a worker whose probe prints `probe_output`."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "nvidia-ctk").write_text("#!/bin/sh\nexit 0\n")
    (bin_dir / "nvidia-smi").write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        "  *--query-gpu=uuid*) echo GPU-0123abcd-4567-89ef ;;\n"
        "  *) echo '| NVIDIA-SMI 570.195.03  Driver Version: 570.195.03  "
        "CUDA Version: 12.8 |' ;;\n"
        "esac\n"
    )
    (bin_dir / "docker").write_text(
        "#!/bin/sh\n"
        f'echo "$*" >> "{tmp_path}/docker.log"\n'
        'case "$1" in\n'
        "  info) exit 0 ;;\n"
        f"  image) echo {IMAGE} ;;\n"
        f"  run) printf '%s\\n' '{probe_output}'; exit {probe_rc} ;;\n"
        "esac\n"
    )
    for tool in bin_dir.iterdir():
        tool.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}


def run(script, env):
    done = subprocess.run(
        ["bash", "-s"], input=script.encode(), env=env, capture_output=True, check=False
    )
    return done.returncode, done.stdout


def test_the_check_reads_the_driver_cuda_and_starts_nothing(tmp_path):
    env = fake_host(tmp_path, "unused", 1)
    code, stdout = run(check_script(IMAGE), env)
    assert code == 0
    assert driver_cuda(stdout) == "12.8"
    log = (tmp_path / "docker.log").read_text()
    assert "run " not in log and "info" in log


class FakeSSH:
    def __init__(self, code, stdout=b""):
        self.result = (code, stdout)

    def run(self, script, *, timeout):
        return self.result


def transport(code, stdout=b""):
    from carbon.compute.remote_transport import SSHDocker

    return SSHDocker(FakeSSH(code, stdout), fingerprint=lambda _id: None)


IMAGE_ID = SimpleNamespace(image_id=IMAGE)


def test_the_transport_reports_the_driver_cuda():
    check = transport(0, b"carbon-driver-cuda 12.8\n").check(IMAGE_ID)
    assert check["worker_image"] == "present" and check["driver_cuda"] == "12.8"
    assert "driver_cuda" not in transport(0).check(IMAGE_ID)
    missing = transport(NO_WORKER_IMAGE, b"carbon-driver-cuda 13.0\n").check(IMAGE_ID)
    assert missing["worker_image"] == "missing" and missing["driver_cuda"] == "13.0"
    with pytest.raises(RemoteMachineError) as refused:
        transport(NO_NVIDIA_TOOLKIT).check(IMAGE_ID)
    assert refused.value.code == "no_nvidia_container_toolkit"


def test_setup_warns_when_a_worker_needs_a_newer_cuda_than_the_driver():
    from test_gpu_per_backend import JAX, TORCH

    from carbon.development_session.gpu_practice import runtime_cuda
    from scripts.dev.miner_launchpad.environment_setup import driver_warning

    assert runtime_cuda("jax-cuda13-py311") == runtime_cuda("torch-cu130-py311") == 13
    warning = driver_warning(JAX, "12.8")
    assert warning["result"] == "gpu_driver_older_than_worker"
    assert (warning["backend"], warning["driver_cuda"], warning["worker_cuda"]) == (
        "jax",
        "12.8",
        13,
    )
    assert "update the driver" in warning["next_step"]
    assert "forward-compatibility" in warning["next_step"]
    assert driver_warning(TORCH, "12.8")["backend"] == "pytorch"
    assert driver_warning(JAX, "13.0") is None
    assert driver_warning(JAX, None) is None


def test_a_build_job_that_names_the_driver_fails_typed():
    stderr = b"...\ncudaErrorInsufficientDriver: CUDA driver version is insufficient\n"
    assert remote_runner.DRIVER_TOO_OLD.search(stderr)
    assert not remote_runner.DRIVER_TOO_OLD.search(b"Traceback: ValueError: shape")


def test_the_practice_records_the_driver_as_its_reason():
    from carbon.development_session.catalog_gpu import FALLBACK_WORDS, backend_record
    from carbon.development_session.gpu_practice import _gpu_failure_note

    driver = RemoteJobFailure("run", remote_runner.GPU_DRIVER_TOO_OLD)
    assert _gpu_failure_note(driver) == "gpu_driver_too_old"
    assert _gpu_failure_note(RemoteJobFailure("run", "x")) == "gpu_build_failed"
    record = backend_record(None, None, "gpu_driver_too_old", None)
    assert record["gpu_note"] == "gpu_driver_too_old"
    assert "NVIDIA driver is older" in record["fallback"]
    assert "gpu_driver_too_old" in FALLBACK_WORDS


def test_setup_status_lists_a_worker_that_could_not_use_the_gpu():
    from scripts.dev.miner_launchpad import setup_operations

    probe = {
        "backend": "jax",
        "result": "gpu_driver_older_than_worker",
        "next_step": "update the driver",
    }

    class Setup:
        def state(self):
            steps = {
                name: {"checked": True}
                for name in ("signer", "agent", "inference", "review")
            }
            steps["compute"] = {"checked": True, "check": {"gpu_warnings": [probe]}}
            steps["review"]["profile_written"] = True
            return {"steps": steps, "registered_hotkey": "5Hotkey"}

    view = setup_operations.status(Setup(), door=setup_operations.MCP)
    assert {
        "code": "gpu_driver_older_than_worker",
        "backend": "jax",
        "next_step": "update the driver",
    } in view["warnings"]


@pytest.fixture(autouse=True)
def _uv_image_here(monkeypatch):
    """The pinned uv image is present unless a test says otherwise, so a GPU
    failure's note never depends on this machine's Docker."""
    from carbon.development_session import gpu_practice

    monkeypatch.setattr(gpu_practice, "_uv_image_present", lambda: True)

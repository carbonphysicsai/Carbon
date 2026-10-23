"""A catalog practice this host cannot run says so in words (gate2c).

On the A6000 pod (driver CUDA 12.8), jno.fno1d - a JAX entry with a GPU
build and no CPU build installed - failed its GPU build with
cudaErrorInsufficientDriver and the miner saw nothing: no experiment, no
refusal. And on M1 a missing pinned uv image read only as a silent CPU
fallback. Now:
- a GPU build that did not run, with no CPU build to practise instead, is
  PRACTICE_UNAVAILABLE with the GPU's reason in words (the driver, the uv
  image, or the build), the task completed with it - never FAILED_INFRA;
- a GPU failure whose preparation lacked the pinned uv image is named
  `gpu_uv_image_missing`, with the pull command.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest
from test_research_budget_refusal_typing import State, compose, product, run

from carbon.compute.remote_job import RemoteJobFailure
from carbon.development_session import gpu_practice
from carbon.development_session.gpu_practice import (
    PracticeUnavailable,
    _gpu_failure_note,
)
from carbon.development_session.library_bundles import UV_IMAGE
from carbon.development_session.research_tasks import (
    PRACTICE_UNAVAILABLE_OUTCOME,
    practice_unavailable_result,
)


def test_the_failure_note_names_the_cause_the_miner_can_act_on(monkeypatch):
    monkeypatch.setattr(gpu_practice, "_uv_image_present", lambda: False)
    assert _gpu_failure_note(RuntimeError("prep failed")) == "gpu_uv_image_missing"
    # The driver, named by the job itself, comes first.
    driver = RemoteJobFailure("run", "gpu_driver_too_old")
    assert _gpu_failure_note(driver) == "gpu_driver_too_old"
    monkeypatch.setattr(gpu_practice, "_uv_image_present", lambda: True)
    assert _gpu_failure_note(RuntimeError("prep failed")) == "gpu_build_failed"


def test_the_uv_check_reads_this_machine_s_docker(monkeypatch):
    seen = []

    def docker(argv, **kwargs):
        seen.append(argv)
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(subprocess, "run", docker)
    assert gpu_practice._uv_image_present() is False
    assert seen == [["docker", "image", "inspect", UV_IMAGE]]

    def unreachable(argv, **kwargs):
        raise OSError("no docker")

    monkeypatch.setattr(subprocess, "run", unreachable)
    # Docker cannot say: no other failure is misnamed as the uv image.
    assert gpu_practice._uv_image_present() is True


@pytest.mark.parametrize(
    ("code", "words"),
    [
        ("gpu_driver_too_old", "NVIDIA driver is older"),
        ("gpu_uv_image_missing", "docker pull ghcr.io/astral-sh/uv:0.12.7@sha256:"),
        ("gpu_build_failed", "GPU build failed"),
    ],
)
def test_the_unavailable_result_says_why_and_what_to_do(code, words):
    result = practice_unavailable_result(PracticeUnavailable(code))
    assert result["outcome"] == PRACTICE_UNAVAILABLE_OUTCOME == "PRACTICE_UNAVAILABLE"
    assert result["code"] == code
    assert words in result["correction"]
    assert "no CPU build here" in result["correction"]
    assert result["nothing_scored"] is True and result["authority_granted"] is False


def test_an_unavailable_practice_completes_typed_through_the_executor(tmp_path):
    ledger = product(tmp_path)

    def gpu_only(name, workspace):
        raise PracticeUnavailable("gpu_driver_too_old")

    f, p, e = compose(tmp_path, ledger, gpu_only)
    done = run(f, p, 0)
    # Completed with its typed result: never an infrastructure failure.
    assert done.state is State.SUCCEEDED
    assert done.terminal_receipt.infrastructure_failure_class is None
    result = e.public_result(done)["result"]
    assert result["outcome"] == "PRACTICE_UNAVAILABLE"
    assert "NVIDIA driver is older" in result["correction"]

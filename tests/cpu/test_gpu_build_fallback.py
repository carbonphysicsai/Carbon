"""A GPU build that fails for infrastructure runs again on CPU (M1 S5).

On M1, jno.fno1d's GPU preparation succeeded on the miner's remote GPU, then
its build job failed (RemoteJobFailure, FAILED_INFRA) and the miner saw
nothing: no refusal, no experiment. Now the practice runs again on the
entry's CPU build, under its own identity, and says why (`gpu_build_failed`),
as a failed preparation already did. A failure of the miner's own program or
recipe is never retried, and a host with no GPU runs once, as before. The
same helper serves Motor, Cooling and the direct (F08/F02) practices.
"""

from __future__ import annotations

import pytest
from test_gpu_only_entry import JAX_RUNTIME, staged  # noqa: F401
from test_gpu_per_backend import JAX, entry

from carbon.compute.remote_job import RemoteJobFailure
from carbon.development_session.gpu_practice import run_on_device
from carbon.development_session.library_environment_cache import (
    VerifiedLibraryOverlay,
)

OVERLAY = object.__new__(VerifiedLibraryOverlay)


class Parents:
    def for_bundle(self, bundle):
        return ("parent", bundle)


class Practice:
    cache_root = "/cache"

    def __init__(self, workers, *, cpu=True):
        self.gpu_image = workers
        self.cpu = cpu

    def parents(self):
        return Parents()

    def _resolve(self, bundle):
        if bundle == "cpu" and self.cpu:
            return "cpu image"
        raise FileNotFoundError(bundle)


def runner(failure=None):
    calls = []

    def run(trial, built, image, parent, device):
        calls.append((trial, built["source"]["bundle_ref"], image, device))
        if failure is not None and device is not None:
            raise failure
        return {"trial": trial}

    return run, calls


def attempt(practice, run):
    return run_on_device(
        practice,
        "trial-1",
        entry({JAX_RUNTIME}),
        lambda ref: ref,
        lambda bundle, parent, built: OVERLAY,
        run,
    )


def test_an_infrastructure_failure_of_the_gpu_build_runs_the_cpu_build():
    run, calls = runner(RemoteJobFailure("run", "the carrier program failed"))
    result, expanded, parent, accelerator, note = attempt(Practice(JAX), run)
    assert [c[:3] for c in calls] == [
        ("trial-1", JAX_RUNTIME, OVERLAY),
        ("trial-1-cpu", "cpu", "cpu image"),
    ]
    assert calls[0][3] is not None and calls[1][3] is None
    assert result == {"trial": "trial-1-cpu"}
    assert (accelerator, note) == (None, "gpu_build_failed")
    assert expanded["source"]["bundle_ref"] == "cpu" and parent == ("parent", "cpu")


def test_the_gpu_build_s_own_success_is_kept():
    run, calls = runner()
    result, _expanded, _parent, accelerator, note = attempt(Practice(JAX), run)
    assert len(calls) == 1 and accelerator is not None and note is None
    assert result == {"trial": "trial-1"}


def test_a_miner_or_recipe_failure_on_the_gpu_is_never_retried():
    run, calls = runner(ValueError("the recipe's output was refused"))
    with pytest.raises(ValueError):
        attempt(Practice(JAX), run)
    assert len(calls) == 1


def test_no_cpu_child_after_a_failed_gpu_build_is_unavailable_typed(monkeypatch):
    from carbon.development_session import gpu_practice

    monkeypatch.setattr(gpu_practice, "_uv_image_present", lambda: True)
    run, _calls = runner(RemoteJobFailure("run", "x"))
    with pytest.raises(gpu_practice.PracticeUnavailable) as refused:
        attempt(Practice(JAX, cpu=False), run)
    assert refused.value.code == "gpu_build_failed"
    driver = runner(RemoteJobFailure("run", "gpu_driver_too_old"))[0]
    with pytest.raises(gpu_practice.PracticeUnavailable) as refused:
        attempt(Practice(JAX, cpu=False), driver)
    assert refused.value.code == "gpu_driver_too_old"


def test_a_host_with_no_gpu_runs_once_on_cpu():
    run, calls = runner()
    _result, _e, _p, accelerator, note = attempt(Practice(None), run)
    assert [c[1] for c in calls] == ["cpu"] and accelerator is None and note is None


@pytest.fixture(autouse=True)
def _uv_image_here(monkeypatch):
    """The pinned uv image is present unless a test says otherwise, so a GPU
    failure's note never depends on this machine's Docker."""
    from carbon.development_session import gpu_practice

    monkeypatch.setattr(gpu_practice, "_uv_image_present", lambda: True)

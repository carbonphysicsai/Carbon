"""An entry served on this host's GPU alone is practised there (M1 S5).

On M1 (a --gpu --pytorch install, CPU worker PyTorch), jno.fno1d's practice
was refused `backend_not_served` before it started: its CPU child was not
installed, though its JAX GPU build was staged and the JAX GPU worker paired.
Before dispatch, an entry whose GPU build is staged for one of the host's GPU
workers is not refused (`gpu_build_staged`); if that GPU build then does not
run and there is no CPU child, the practice is refused typed
`backend_not_served`, never an untyped failure. The same for every Challenge.
"""

from __future__ import annotations

import pytest
from test_gpu_per_backend import JAX, TORCH, entry

from carbon.development_session import gpu_practice
from carbon.development_session.gpu_practice import (
    DirectParentRefused,
    device_build,
    gpu_build_staged,
)

JAX_RUNTIME = "jax-cuda13-py311"


class Parents:
    def for_bundle(self, bundle):
        return ("parent", bundle)


class GpuOnlyPractice:
    """A host with GPU workers and no CPU child for the entry."""

    cache_root = "/cache"

    def __init__(self, workers):
        self.gpu_image = workers

    def parents(self):
        return Parents()

    def _resolve(self, bundle):
        raise FileNotFoundError(bundle)


@pytest.fixture
def staged(monkeypatch):
    """The JAX GPU build's material is staged; nothing else is."""
    from carbon.development_session import library_environment_cache

    def inspect(cache_root, bundle):
        if bundle != JAX_RUNTIME:
            raise FileNotFoundError(bundle)
        return cache_root

    monkeypatch.setattr(
        library_environment_cache, "inspect_staged_bundle_material", inspect
    )


def test_a_staged_gpu_build_on_a_host_worker_admits_the_entry(staged):
    jno = entry({JAX_RUNTIME})
    assert gpu_build_staged(GpuOnlyPractice((JAX, TORCH)), jno, lambda ref: ref)
    assert gpu_build_staged(GpuOnlyPractice(JAX), jno, lambda ref: ref)


@pytest.mark.parametrize("workers", [TORCH, None], ids=["torch-only", "no-gpu"])
def test_without_its_backend_s_worker_or_staged_build_it_is_still_refused(
    staged, workers
):
    jno = entry({JAX_RUNTIME})
    assert not gpu_build_staged(GpuOnlyPractice(workers), jno, lambda ref: ref)


def test_an_unstaged_gpu_build_does_not_admit_it(monkeypatch):
    from carbon.development_session import library_environment_cache

    def missing(cache_root, bundle):
        raise FileNotFoundError(bundle)

    monkeypatch.setattr(
        library_environment_cache, "inspect_staged_bundle_material", missing
    )
    assert not gpu_build_staged(
        GpuOnlyPractice(JAX), entry({JAX_RUNTIME}), lambda ref: ref
    )


def test_a_gpu_build_that_does_not_run_with_no_cpu_child_is_refused_typed():
    def failing_overlay(bundle, parent, expanded):
        raise RuntimeError("the GPU preparation failed")

    with pytest.raises(DirectParentRefused) as refused:
        device_build(
            GpuOnlyPractice(JAX),
            entry({JAX_RUNTIME}),
            lambda ref: ref,
            failing_overlay,
        )
    assert refused.value.code == "backend_not_served"


def test_with_no_gpu_attempt_a_missing_cpu_child_raises_as_before():
    with pytest.raises(FileNotFoundError):
        device_build(GpuOnlyPractice(None), entry(set()), lambda ref: ref)


def test_the_gpu_build_runs_when_it_is_prepared(monkeypatch):
    from carbon.development_session.library_environment_cache import (
        VerifiedLibraryOverlay,
    )

    overlay = object.__new__(VerifiedLibraryOverlay)
    built = device_build(
        GpuOnlyPractice(JAX),
        entry({JAX_RUNTIME}),
        lambda ref: ref,
        lambda bundle, parent, expanded: overlay,
    )
    assert built[2] is overlay and built[4] is not None and built[5] is None
    assert gpu_practice.gpu_runtimes(JAX) == (JAX_RUNTIME,)

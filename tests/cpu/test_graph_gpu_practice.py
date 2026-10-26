"""A graph-route practice uses the miner's GPU when the host has one.

On a GPU machine a catalog or graph practice completed but ran on the CPU (GPU
at 0 %), because the graph route had no GPU path at all. The graph route is
JAX, so a host that declares GPU practice now runs the graph's build and
inference on its JAX GPU worker (speed only, labelled, never official); a
failed GPU attempt practises on the CPU and says why, and the miner's own
failures are never retried. "Test my GPU" names the real run's device and a
writable TMPDIR so JAX is not reported absent on a working GPU.
"""

from __future__ import annotations

import pytest
from test_battery_gpu_practice import gpu_image
from test_f08_f02_graph_adapters import (
    SERVED,
    _binding,
    _case,
    _image,
    _local_runner,
    _train,
    adapter,
    posix,
)

from carbon.compute import remote_machine
from carbon.development_session import catalog_gpu, gpu_practice
from carbon.development_session import (
    direct_graph_construction_worker as graph_worker,
)
from carbon.development_session.research_carrier import (
    MINER_GPU,
    MinerProgramFailure,
)
from carbon.reconstruction import torch_profile

JAX = gpu_image("9")
TORCH = gpu_image("8", lock=torch_profile.GPU_LOCK_DIGEST)
CPU = object()


class Practice:
    parent = CPU

    def __init__(self, workers):
        self.gpu_image = workers


# --- the device ----------------------------------------------------------------


@pytest.mark.parametrize(
    "workers,expected",
    [
        (None, (CPU, None, None)),
        (JAX, (JAX, MINER_GPU, None)),
        ((TORCH, JAX), (JAX, MINER_GPU, None)),
        ((JAX, TORCH), (JAX, MINER_GPU, None)),
        (TORCH, (CPU, None, gpu_practice.GRAPH_GPU_WORKER_MISSING)),
    ],
)
def test_the_graph_route_runs_on_the_jax_gpu_worker_when_there_is_one(
    workers, expected
):
    assert gpu_practice.graph_device(Practice(workers)) == expected


def test_a_pytorch_only_host_says_in_words_why_it_ran_on_the_cpu():
    record = catalog_gpu.backend_record(
        None, None, gpu_practice.GRAPH_GPU_WORKER_MISSING, None
    )
    assert record["fallback"].startswith("Ran on CPU: your graph practises on the JAX")


# --- the run -------------------------------------------------------------------


def _run(calls, failure=None):
    def run(trial, image, device):
        calls.append((trial, image, device))
        if failure is not None and device is not None:
            raise failure
        return {"trial": trial}

    return run


def test_a_gpu_host_runs_the_graph_once_on_the_gpu():
    calls = []
    result = gpu_practice.run_graph_on_device(Practice(JAX), "t1", _run(calls))
    assert result == ({"trial": "t1"}, JAX, MINER_GPU, None)
    assert calls == [("t1", JAX, MINER_GPU)]


def test_a_cpu_host_runs_once_as_before():
    calls = []
    result = gpu_practice.run_graph_on_device(Practice(None), "t1", _run(calls))
    assert result == ({"trial": "t1"}, CPU, None, None)
    assert calls == [("t1", CPU, None)]


@pytest.mark.parametrize(
    "failure", [RuntimeError("gpu"), OSError("gpu"), ValueError("x")]
)
def test_a_device_failure_practises_on_the_cpu_under_its_own_identity(
    failure, monkeypatch
):
    monkeypatch.setattr(gpu_practice, "_uv_image_present", lambda: True)
    calls = []
    result, image, accelerator, note = gpu_practice.run_graph_on_device(
        Practice(JAX), "t1", _run(calls, failure)
    )
    assert (image, accelerator, note) == (CPU, None, "gpu_build_failed")
    assert result == {"trial": "t1-cpu"}
    assert calls == [("t1", JAX, MINER_GPU), ("t1-cpu", CPU, None)]


def test_the_miners_own_failure_or_the_campaigns_limit_is_never_retried():
    from carbon.development_session.construction_recipe import RecipeRefused
    from carbon.development_session.research_ledger import LedgerRefusal

    typed = MinerProgramFailure(
        {
            "schema": "carbon.autoresearch.miner-program-failure.v1",
            "failure_code": "reconstruction.worker.runtime.failed",
            "observation": "WORKER_MEMORY_LIMIT_REACHED",
        }
    )
    for failure in (
        typed,
        RecipeRefused("graph_invalid"),
        LedgerRefusal.__new__(LedgerRefusal),
    ):
        calls = []
        with pytest.raises(type(failure)):
            gpu_practice.run_graph_on_device(Practice(JAX), "t1", _run(calls, failure))
        assert calls == [("t1", JAX, MINER_GPU)]


# --- the plumbing --------------------------------------------------------------


@posix
@pytest.mark.parametrize("device", [None, MINER_GPU])
def test_the_gpu_reaches_the_build_and_the_inference_child(device, tmp_path):
    from types import SimpleNamespace

    import numpy as np

    from carbon.development_session.profile import canonical

    key = SERVED[0]
    recipe, raw_manifest, files, staging = _case(key, {"steps": 16})
    raw_train, inputs, _targets = _train(key)
    query = np.ascontiguousarray(inputs[:3])
    spec = adapter.SPECS[key]
    local = _local_runner()
    seen = []

    def runner(ledger, *, identity, **kwargs):
        seen.append((kwargs["provenance"], kwargs.get("accelerator")))
        kwargs.pop("accelerator", None)
        return local(ledger, identity=identity, **kwargs)

    from test_f08_f02_graph_adapters import PUBLIC

    graph_worker.reconstruct_and_infer_graph_public(
        SimpleNamespace(root=tmp_path),
        owner="test",
        identity="test",
        image=_image(),
        recipe=recipe,
        challenge_binding=_binding(key),
        limits_document=PUBLIC[key[0]].construction_limits_document(*key),
        source_envelope=canonical(staging.envelope(raw_manifest, files)),
        train=raw_train,
        inputs=query,
        expected_output_shape=(3, spec.outputs),
        allowlist_bytes=adapter.served_allowlist_bytes(*key),
        seed=0,
        runner=runner,
        adapter_id=spec.adapter_id,
        **({} if device is None else {"accelerator": device}),
    )
    assert seen == [
        (graph_worker.BUILD_PROVENANCE, device),
        (graph_worker.INFERENCE_PROVENANCE, device),
    ]


# --- "Test my GPU" -------------------------------------------------------------


@pytest.mark.parametrize("backend", ["jax", "pytorch"])
def test_test_my_gpu_names_the_real_runs_device_and_a_writable_tmpdir(backend):
    script = remote_machine.gpu_test_script("sha256:" + "9" * 64, backend)
    assert "--env JAX_PLATFORMS=cuda" in script
    assert "--env TMPDIR=/scratch" in script
    assert "--read-only" in script and "--network none" in script

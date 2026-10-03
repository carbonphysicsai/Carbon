"""A real CUDA kernel through the miner lane (JULIA-GPU-01 slice 3).

GPU HOST ONLY. It runs where a host device record is installed
(`scripts/dev/carbon_accelerator.py prepare`) and is skipped everywhere else,
including CI, which has no GPU. It needs the built authored-Julia image, as the
Julia service suite does (`CARBON_JULIA_WORKER_MANIFEST`).

`run_julia` with the miner's own GPU runs the composed Julia image in the
isolated miner lane, with exactly the host's recorded device attached. The
program checks the kernel's result against the host's own arithmetic and times
the first kernel (which compiles it) and a second one. With
`CARBON_JULIA_GPU_EVIDENCE=<file>` the measured record is written there.

Self-reported research on the miner's own machine. Speed only, never
evidence the validator reads; nothing here is qualified.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests/cpu")]

from test_authored_julia import prepared

from carbon.development_session.julia_analysis import (
    build_julia_analysis_image,
    run_julia,
)
from carbon.development_session.research_carrier import MINER_GPU
from carbon.reconstruction.worker.model import WorkerFailure

KERNEL = r"""
using CUDA
started = time()
loaded = CUDA.functional()
device = CUDA.device()
a = CUDA.rand(Float32, 1 << 20)
b = 2f0 .* a
total = sum(b)
CUDA.synchronize()
first_kernel_s = time() - started
expected = 2f0 * sum(Array(a))
again = time()
second = sum(CUDA.ones(Float32, 1 << 20) .+ 1f0)
CUDA.synchronize()
second_kernel_s = time() - again
open("/scratch/output/result.json", "w") do io
    print(io, "{",
        "\"functional\":", loaded, ",",
        "\"device\":\"", CUDA.name(device), "\",",
        "\"capability\":\"", CUDA.capability(device), "\",",
        "\"driver\":\"", CUDA.driver_version(), "\",",
        "\"runtime\":\"", CUDA.runtime_version(), "\",",
        "\"sum_matches_host\":", isapprox(total, expected; rtol=1f-4), ",",
        "\"second_sum\":", second, ",",
        "\"first_kernel_s\":", first_kernel_s, ",",
        "\"second_kernel_s\":", second_kernel_s,
        "}")
end
"""


@pytest.fixture(scope="module")
def device():
    from carbon.reconstruction.worker.accelerator_runtime import host_device

    try:
        return host_device()
    except WorkerFailure:
        pytest.skip("GPU host only: no host device record is installed here")


@pytest.fixture(scope="module")
def image(device, tmp_path_factory):
    return build_julia_analysis_image(
        Path(os.environ["CARBON_JULIA_WORKER_MANIFEST"]),
        Path(
            os.environ.get(
                "CARBON_AUTHORED_JULIA_IMAGE_ROOT",
                str(tmp_path_factory.mktemp("julia-image")),
            )
        ),
    )


def test_a_real_cuda_kernel_runs_through_the_miner_lane(device, image, tmp_path):
    ledger, _ = prepared(tmp_path, image=image)
    started = time.monotonic()
    try:
        result = run_julia(
            ledger,
            owner="test-miner",
            identity="julia-gpu-kernel",
            source=KERNEL,
            files={},
            image=image,
            seconds=1800,
            environment="current",
            accelerator=MINER_GPU,
        )
    except WorkerFailure as exc:
        pytest.fail(exc.private_diagnostic.decode("utf-8", errors="replace"))
    wall_s = time.monotonic() - started
    snapshot = ledger.root / result["operation"] / "snapshot"
    values = json.loads((snapshot / "result.json").read_bytes())
    assert values["functional"] is True
    assert values["sum_matches_host"] is True
    assert values["second_sum"] == 2 * (1 << 20)
    assert values["device"] == device.device_kind
    record = {
        "schema": "carbon.julia-gpu.lane-run.v1",
        "ticket": "JULIA-GPU-01 slice 3",
        "lane": "miner research lane, isolated container, one GPU by UUID",
        "image": image.image_id,
        "depot_digest": image.depot.depot_digest,
        "device_record_digest": device.digest,
        "host": {
            "device_kind": device.device_kind,
            "platform": getattr(device, "platform", None),
        },
        "observed": values,
        "operation_wall_s": round(wall_s, 3),
        "provenance": "MINER_SELF_REPORTED",
        "qualification": False,
    }
    evidence = os.environ.get("CARBON_JULIA_GPU_EVIDENCE")
    if evidence:
        Path(evidence).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

"""TORCH-POD-01: battery's PyTorch builds on Carbon's Graphite pods.

One mechanism with JAX's: the same practice program and staged files, the
pod's image, CUDA versions, platform and probe chosen by the job's backend,
and the pod's PyTorch build checked against Carbon's own rebuild identity.
JAX's programs, job configuration and pod environment stay byte for byte.
No pod, key, network or spend: the GPU check at the end runs only inside the
released torch-gpu image with CUDA (`CARBON_REQUIRE_CUDA=1`).
"""

from __future__ import annotations

import importlib.util
import json
import os
import threading
from pathlib import Path

import pytest

from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import pod_phase, pods
from carbon.battery import rebuild_identity
from carbon.battery.research import SCAFFOLD
from carbon.challenge_validator import scoring as cs
from carbon.challenge_validator.battery_scoring import (
    SCORING_VERSION,
    SERVED_BACKENDS,
    BatteryScoring,
)
from carbon.development_session import battery_gpu as bg
from carbon.development_session.profile import digest

REPOSITORY = Path(__file__).resolve().parents[2]
TORCH = {**SCAFFOLD, "parameters": {**SCAFFOLD["parameters"], "backend": "pytorch"}}
REQUIRED = os.environ.get("CARBON_REQUIRE_CUDA") == "1"


@pytest.fixture(scope="module")
def battery():
    return BatteryScoring()


# -- the program: one practice program, the runtime record by backend ----------------------
def test_jax_pod_programs_are_unchanged_and_pytorch_is_v3():
    assert bg.pod_program("fno") == bg.pod_program("fno", "jax") == (bg.GPU_PROGRAM, {})
    assert bg.pod_program("knn")[0] == bg.KNN_GPU_PROGRAM
    torch_program, extra = bg.pod_program("fno", "pytorch")
    assert torch_program == bg.TORCH_GPU_PROGRAM and extra == {}
    assert bg.program_version(digest(bg.GPU_PROGRAM.encode())) == bg.PROGRAM_V1
    assert bg.program_version(digest(bg.TORCH_GPU_PROGRAM.encode())) == bg.PROGRAM_V3
    # One mechanism: the PyTorch program is the practice program plus its
    # runtime record, exactly as JAX's v1 is.
    assert bg.TORCH_GPU_PROGRAM.startswith(bg.PROGRAM)
    assert bg.GPU_PROGRAM.startswith(bg.PROGRAM)
    with pytest.raises(ValueError):
        bg.pod_program("fno", "numpy")


def test_the_scoring_record_is_versioned_and_serves_pytorch(battery):
    assert SCORING_VERSION == "battery-scoring-v2-pytorch"
    assert battery.served_backends == ("jax", "pytorch")
    assert SERVED_BACKENDS["battery-scoring-v1"] == ("jax",)
    # Development levels train with their own JAX programs.
    assert battery.development_backends == ("jax",)


# -- identity parity: the pod builds exactly what Carbon rebuilds ------------------------------
def test_a_pods_pytorch_build_is_carbons_rebuild_identity(battery):
    admitted = ex.admit(TORCH, 0, scoring=battery)
    assert battery.backend(admitted) == "pytorch"
    assert admitted["program"] == digest(bg.TORCH_GPU_PROGRAM.encode())
    for staged in ("battery-torch-training.py", "battery-torch-families.py"):
        assert staged in admitted["staged"]
    # The pod builds through the same Challenge scoring, from the job alone.
    on_pod, files, program = pod_phase.built_record(
        TORCH, admitted["contract_digest"], 0, scoring=battery
    )
    assert cs.rebuild_differences(admitted, on_pod) == []
    assert pod_phase.pinned(
        on_pod, {"files": admitted["staged"], "program": admitted["program"]}
    )
    assert digest(program.encode()) == admitted["program"]
    assert {name: digest(body) for name, body in files.items()} == admitted["staged"]


def test_a_jax_build_keeps_its_program_and_job(battery):
    admitted = ex.admit(SCAFFOLD, 0, scoring=battery)
    assert admitted["program"] == digest(bg.GPU_PROGRAM.encode())
    job = pods.PodJob("i", SCAFFOLD, "c", 0, {}, 30, 600)
    assert job.backend == "jax" and "backend" not in job.config(1)
    torch_job = pods.PodJob("i", TORCH, "c", 0, {}, 30, 600, backend="pytorch")
    assert torch_job.config(1)["backend"] == "pytorch"
    assert pods.job_backend("pytorch") == "pytorch"
    assert pods.job_backend("jax") == pods.job_backend("numpy") == "jax"


# -- the pod: image, CUDA versions, platform and probe by backend --------------------------
def _backend():
    backend = object.__new__(pods.RunPodPods)
    backend.code_ref, backend.manifest = "0" * 40, {}
    backend.economics = pods.prices()
    backend.cuda_versions = ("13.0",)
    backend.boot = "pass"
    backend.clock = lambda: 1_000_000.0
    backend._record_lock = threading.Lock()
    backend.repository = REPOSITORY
    return backend


RECORD = {"intent_id": "i", "token": "t" * 32, "deadline_at": 1_001_800}


def test_a_pytorch_pod_runs_the_torch_image_on_cuda_only():
    from scripts.dev.exam_design.runpod import pod_control
    from scripts.dev.exam_design.runpod.a40_acceptance import IMAGES

    backend = _backend()
    jax_job = pods.PodJob("i", SCAFFOLD, "c", 0, {"files": {}}, 30, 600)
    torch_job = pods.PodJob(
        "i", TORCH, "c", 0, {"files": {}}, 30, 600, backend="pytorch"
    )
    jax_spec = backend.pod_spec(jax_job, {**RECORD, "allowed_cuda_versions": ["13.0"]})
    torch_spec = backend.pod_spec(
        torch_job, {**RECORD, "allowed_cuda_versions": ["13.0"]}
    )
    assert jax_spec.image == pod_control.IMAGE == pods.pod_image("jax")
    assert torch_spec.image == IMAGES["pytorch"] == pods.pod_image("pytorch")
    assert dict(jax_spec.env)["JAX_PLATFORMS"] == "cuda,cpu"
    assert dict(torch_spec.env)["JAX_PLATFORMS"] == "cuda"
    # PyTorch's CUDA rebuild is bound to the rented device kind and the pinned
    # CUDA controls; JAX's environment gains nothing.
    from carbon.reconstruction.accelerators import GPU_DETERMINISM_ENVIRONMENT

    torch_env, jax_env = dict(torch_spec.env), dict(jax_spec.env)
    assert torch_env["CARBON_ACCELERATOR_DEVICE_KIND"] == backend.economics["gpu"]
    assert all(torch_env[k] == v for k, v in GPU_DETERMINISM_ENVIRONMENT.items())
    assert "CARBON_ACCELERATOR_DEVICE_KIND" not in jax_env
    assert set(torch_env) - set(jax_env) == {"CARBON_ACCELERATOR_DEVICE_KIND"}
    assert json.loads(dict(torch_spec.env)["PHASE_CONFIG"])["backend"] == "pytorch"
    assert "backend" not in json.loads(dict(jax_spec.env)["PHASE_CONFIG"])
    with pytest.raises(pods.PodFailure):
        pods.pod_image("numpy")


def test_pytorch_cuda_versions_come_from_the_torch_lock():
    versions = pods.allowed_cuda_versions(REPOSITORY, "pytorch")
    assert versions and all(v.startswith("13.") for v in versions)
    major, minor = pods.RUNPOD_CUDA_CEILING
    assert versions[-1] == f"{major}.{minor}"
    assert _backend()._cuda_versions("pytorch") == versions
    assert _backend()._cuda_versions("jax") == ("13.0",)


def test_the_torch_probe_requires_the_bound_device_kind():
    assert "CARBON_ACCELERATOR_DEVICE_KIND" in pod_phase.TORCH_PROBE
    assert pod_phase._PROBE_FIELDS["device_kind_bound"] is bool


def test_the_pod_probes_the_jobs_backend(tmp_path, monkeypatch):
    seen = []

    def probe(code=None):
        seen.append(code)
        return {"ok": False, "error_type": "probe_double"}

    monkeypatch.setattr(pod_phase, "probe_environment", probe)
    assert (
        pod_phase.run({"backend": "pytorch"}, tmp_path / "a")
        == pod_phase.EXIT_ENVIRONMENT
    )
    assert pod_phase.run({}, tmp_path / "b") == pod_phase.EXIT_ENVIRONMENT
    assert seen == [pod_phase.TORCH_PROBE, pod_phase.PROBE]


# -- the GPU check: inside the released torch-gpu image -------------------------------------
_HAS_TORCH = importlib.util.find_spec("torch") is not None


def _cuda():
    if not _HAS_TORCH:
        return False
    import torch

    return torch.cuda.is_available()


@pytest.mark.skipif(
    not (_cuda() or REQUIRED), reason="needs the torch-gpu image with CUDA"
)
def test_the_pytorch_pod_phase_repeats_on_the_gpu(battery, tmp_path, monkeypatch):
    """Run the pod phase itself twice, as a PyTorch pod does: same probe,
    same program, same pinned files. Predictions and fit are bit-identical,
    and the runtime record is a GPU device class Carbon's identity reads."""
    if REQUIRED and not _cuda():
        pytest.fail("CARBON_REQUIRE_CUDA=1 but no CUDA device")
    import torch

    from carbon.reconstruction.accelerators import GPU_DETERMINISM_ENVIRONMENT

    # The pod's own environment (`RunPodPods._env` for a PyTorch job), bound
    # to the device this host has.
    monkeypatch.setenv("JAX_PLATFORMS", "cuda")
    for key, value in GPU_DETERMINISM_ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("CARBON_ACCELERATOR_DEVICE_KIND", torch.cuda.get_device_name(0))
    admitted = ex.admit(TORCH, 0, scoring=battery)
    cfg = {
        "strategy": TORCH,
        "contract_digest": admitted["contract_digest"],
        "seed": 0,
        "expected": {"files": admitted["staged"], "program": admitted["program"]},
        "seconds": battery.work_seconds(),
        "backend": "pytorch",
    }
    runs = []
    for n in range(2):
        out = tmp_path / f"run{n}"
        assert pod_phase.run(cfg, out, root=REPOSITORY) == 0, (
            out / "program.log"
        ).read_text()
        fit = json.loads((out / "fit.json").read_text())
        # Wall-clock fields (`train_s`, `compile_s`) are timings, not the build.
        runs.append(
            {
                "predictions": (out / "predictions.json").read_bytes(),
                "fit": {k: v for k, v in fit.items() if not k.endswith("_s")},
            }
        )
        runtime = json.loads((out / "runtime.json").read_text())
        assert runtime["framework"] == "pytorch"
        assert rebuild_identity.from_runtime(runtime)["device_class"].startswith("gpu:")
    assert runs[0]["fit"].get("params_sha256")
    assert runs[0] == runs[1]


def test_the_pod_runner_reads_the_gpu_environment_through_the_execution_side():
    """Graphite never imports the accelerator profile
    (test_protected_material_isolation); the pod program module supplies it."""
    import ast

    tree = ast.parse(
        (REPOSITORY / "carbon/agent_campaign/graphite/pods.py").read_text()
    )
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "carbon.reconstruction.accelerators" not in imported
    env = bg.torch_pod_environment("NVIDIA A40")
    assert env["CARBON_ACCELERATOR_DEVICE_KIND"] == "NVIDIA A40"
    with pytest.raises(ValueError):
        bg.torch_pod_environment("")

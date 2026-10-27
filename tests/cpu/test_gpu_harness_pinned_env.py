"""The GPU repeat-harness findings A, B and C (Validator, 2026-10-26): a GPU harness takes its environment from
`accelerators.pinned_environment` alone, names its backend explicitly and refuses a non-GPU one by
a typed code, and does not compare allocator bookkeeping."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from carbon.reconstruction import accelerators

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/dev"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


repeat = _load("gpu_repeat")
check = _load("gpu_rebuild_class_check")


def test_the_pinned_environment_is_explicit_and_complete():
    pinned = accelerators.pinned_environment(accelerators.GPU_PROFILE)
    assert pinned["JAX_PLATFORMS"] == "cuda"
    assert pinned["XLA_FLAGS"].split() == list(accelerators.GPU_DETERMINISM_XLA_FLAGS)
    for name, value in accelerators.GPU_DETERMINISM_ENVIRONMENT.items():
        assert pinned[name] == value
    assert "CUDA_VISIBLE_DEVICES" not in pinned  # names no device


def test_the_controllers_worker_environment_is_built_on_it():
    class Device:
        device_uuid, device_kind = "GPU-x", "NVIDIA GeForce RTX 4090"

    import carbon.reconstruction.host_inventory as inventory

    original = inventory.require_host_device
    inventory.require_host_device = lambda device, profile: None
    try:
        worker = accelerators.worker_environment(
            accelerators.GPU_PROFILE,
            accelerators.AcceleratorRole.MINER_RESEARCH,
            host_device=Device(),
        )
    finally:
        inventory.require_host_device = original
    pinned = accelerators.pinned_environment(accelerators.GPU_PROFILE)
    assert {k: worker[k] for k in pinned} == pinned
    assert worker["CUDA_VISIBLE_DEVICES"] == "GPU-x"


def test_both_harnesses_take_their_environment_from_it():
    pinned = accelerators.pinned_environment(accelerators.GPU_PROFILE)
    assert check._pinned_environment() == pinned


def test_the_repeat_harness_sets_it_over_whatever_the_image_exports():
    repo = Path(__file__).resolve().parents[2]
    # a private mapping: setting the pinned matmul precision in THIS process would make every
    # graph a later test lowers carry a non-default `precision`, which graph intake refuses
    exported = {"JAX_PLATFORMS": "cpu", "XLA_FLAGS": "--something_else"}  # the image's
    environment = repeat.pinned(repo, allow_cpu=False, environ=exported)
    assert exported["JAX_PLATFORMS"] == "cuda"
    assert exported["XLA_FLAGS"] == environment["XLA_FLAGS"]
    assert repeat.pinned(repo, allow_cpu=True, environ={})["JAX_PLATFORMS"] == "cpu"


def test_graph_tests_that_run_after_the_harness_tests_still_lower_graphs():
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[2]
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/cpu/test_gpu_harness_pinned_env.py::test_the_repeat_harness_sets_it_over_whatever_the_image_exports",
            "tests/cpu/test_graph_gpu_lane.py::test_a_graph_whose_every_op_repeats_rebuilds_on_the_gpu",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=900,
    )
    assert done.returncode == 0, done.stdout[-1500:]


def _report(path, **entry):
    base = {
        "runtime": "jax-cuda13-py311",
        "gpu": True,
        "repeat_identical": True,
        "first": {
            "device": "gpu",
            "peak_gpu_bytes": 8844800,
            "parameters_sha256": "a",
            "predictions_sha256": "b",
        },
    }
    base.update(entry)
    document = {
        "entries": {"jno.mlp": base},
        "steps": 4,
        "environment_digest": "e1",
    }
    path.write_text(json.dumps(document))
    return path


def test_memory_bookkeeping_is_not_part_of_what_must_repeat(tmp_path, capsys):
    a = _report(tmp_path / "a.json")
    other = json.loads(a.read_text())
    other["entries"]["jno.mlp"]["first"]["peak_gpu_bytes"] = 8849152
    b = tmp_path / "b.json"
    b.write_text(json.dumps(other))
    assert repeat.compare(str(a), str(b)) == 0
    assert json.loads(capsys.readouterr().out) == {"jno.mlp": "PASS"}
    assert repeat.stable({"peak_gpu_bytes": 1, "x": 2}) == {"x": 2}


def test_a_changed_parameter_hash_still_differs(tmp_path, capsys):
    a = _report(tmp_path / "a.json")
    other = json.loads(a.read_text())
    other["entries"]["jno.mlp"]["first"]["parameters_sha256"] = "c"
    b = tmp_path / "b.json"
    b.write_text(json.dumps(other))
    assert repeat.compare(str(a), str(b)) == 1
    assert json.loads(capsys.readouterr().out) == {"jno.mlp": "DIFFER"}


def test_runs_under_different_environments_are_not_compared(tmp_path, capsys):
    a = _report(tmp_path / "a.json")
    other = json.loads(a.read_text())
    other["environment_digest"] = "e2"
    b = tmp_path / "b.json"
    b.write_text(json.dumps(other))
    assert repeat.compare(str(a), str(b)) == 1
    assert "same pinned environment" in capsys.readouterr().out
    legacy = json.loads(a.read_text())
    del legacy["environment_digest"]
    b.write_text(json.dumps(legacy))
    assert (
        repeat.compare(str(b), str(b)) == 1
    )  # a record with no environment proves nothing


def test_a_class_check_lane_that_is_not_on_the_gpu_is_a_typed_refusal(tmp_path):
    pytest.importorskip("jax")
    import jax

    if jax.default_backend() == "gpu":
        pytest.skip("this host has a GPU")
    out = tmp_path / "record.json"
    code = check.main(
        [
            "--keys",
            "f08",
            "--archs",
            "mlp",
            "--steps",
            "1",
            "--no-torch",
            "--skip-cpu-parity",
            "--out",
            str(out),
        ]
    )
    record = json.loads(out.read_text())
    assert code == 1 and record["verdict"] == "NOT_REPEATABLE_OR_NOT_GPU"
    assert "backend_not_gpu" in record["cases"][0]["rebuilds"][0]["error"]

"""The GPU rebuild class check (scripts/dev/gpu_rebuild_class_check.py): its verdicts.

Claims: the same digest from every fresh rebuild on a GPU is GPU_REPEATS; a differing digest puts
that case on the CPU lane and fails the run; a rebuild that did not run on a GPU is not a GPU
result; a child that crashes is a finding, never a pass; a CPU dry run says so; and one real
rebuild (CPU) repeats bit for bit in fresh processes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/dev/gpu_rebuild_class_check.py"
spec = importlib.util.spec_from_file_location("gpu_rebuild_class_check", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def _args(**changes):
    values = {
        "keys": ["f08"],
        "rebuilds": 2,
        "steps": 2,
        "seed": 0,
        "timeout": 60,
        "device": "auto",
        "skip_cpu_parity": True,
        "no_torch": True,
        "out": None,
    }
    values.update(changes)
    return argparse.Namespace(**values)


def _fake(monkeypatch, digests, backend="gpu"):
    calls = iter(digests)

    def run(kind, key, args, *, cpu, tmp, index):
        digest = next(calls)
        if digest is None:
            return {"error": "boom", "predictions": None}
        return {
            "state_digest": digest,
            "backend": "cpu" if cpu else backend,
            "predictions": None,
        }

    monkeypatch.setattr(check, "_run_child", run)


def test_identical_fresh_rebuilds_on_a_gpu_repeat(monkeypatch):
    _fake(monkeypatch, ["sha256:a", "sha256:a"])
    record = check.class_record(_args())
    assert record["verdict"] == "GPU_REPEATS" and record["cpu_lane"] == []
    assert record["cases"][0]["state_digest"] == "sha256:a"


def test_a_differing_digest_puts_the_case_on_the_cpu_lane(monkeypatch):
    _fake(monkeypatch, ["sha256:a", "sha256:b"])
    record = check.class_record(_args())
    assert record["verdict"] == "NOT_REPEATABLE_OR_NOT_GPU"
    assert record["cpu_lane"] == ["graph:f08"]
    assert record["cases"][0]["state_digest"] is None


def test_a_rebuild_that_ran_on_the_cpu_is_not_a_gpu_result(monkeypatch):
    _fake(monkeypatch, ["sha256:a", "sha256:a"], backend="cpu")
    assert check.class_record(_args())["verdict"] == "NOT_REPEATABLE_OR_NOT_GPU"


def test_a_crashing_child_is_never_a_pass(monkeypatch):
    _fake(monkeypatch, [None, None])
    record = check.class_record(_args())
    assert record["verdict"] == "NOT_REPEATABLE_OR_NOT_GPU"
    assert record["cases"][0]["rebuilds"][0]["error"] == "boom"


def test_a_cpu_dry_run_says_so(monkeypatch):
    _fake(monkeypatch, ["sha256:a", "sha256:a"], backend="cpu")
    record = check.class_record(_args(device="cpu"))
    assert record["verdict"] == "REPEATS_ON_CPU_DRY_RUN"


def test_the_flags_are_carbons_one_pinned_definition():
    from carbon.reconstruction.accelerators import (
        GPU_DETERMINISM_ENVIRONMENT,
        GPU_DETERMINISM_XLA_FLAGS,
    )

    flags = check._pinned_environment()
    assert flags["XLA_FLAGS"].split() == list(GPU_DETERMINISM_XLA_FLAGS)
    for name, value in GPU_DETERMINISM_ENVIRONMENT.items():
        assert flags[name] == value


def test_one_real_cpu_rebuild_repeats_in_fresh_processes(tmp_path):
    pytest.importorskip("jax")
    out = tmp_path / "record.json"
    code = check.main(
        [
            "--device",
            "cpu",
            "--keys",
            "f08",
            "--steps",
            "2",
            "--no-torch",
            "--out",
            str(out),
        ]
    )
    record = json.loads(out.read_text(encoding="utf-8"))
    assert code == 0 and record["verdict"] == "REPEATS_ON_CPU_DRY_RUN"
    (case,) = record["cases"]
    assert case["bit_identical"] and len(case["rebuilds"]) == 2

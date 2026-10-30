"""The GPU repeat harness measures the kernel-ridge baselines (the four `prior_krr` twins).

A kernel-ridge build takes no training settings, and its inputs are scaled by the prior's own declared input bounds,
so the smoke gives it no `train_use` settings and draws its inputs uniformly inside those bounds. Entries of other
backbones keep the N(0,1) smoke. The harness also records where the device solve ran.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
KRR = [f"v2.{name}.prior_krr" for name in ("motor", "cooling", "f08", "f02")]


def test_the_krr_smoke_draws_no_train_use_settings_and_uniform_bounded_inputs():
    source = (REPO / "scripts/dev/gpu_repeat.py").read_text(encoding="utf-8")
    assert 'get("backbone") == "krr"' in source
    assert "train_use = {}" in source and 'train_use = {"steps": steps}' in source
    assert "declared_input_bounds" in source


def test_the_four_krr_baselines_build_repeat_identically_and_record_their_solve_device(
    tmp_path,
):
    pytest.importorskip("jax")
    out = tmp_path / "krr.json"
    # a fresh process, as the worker runs it: the pinned environment is set before JAX loads
    subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts/dev/gpu_repeat.py"),
            str(REPO),
            str(out),
            ",".join(KRR),
            "--steps",
            "2",
            "--allow-cpu",
            "--framework",
            "jax",
        ],
        check=True,
        capture_output=True,
    )
    report = json.loads(out.read_text(encoding="utf-8"))
    assert sorted(report["entries"]) == sorted(KRR)
    for catalog_id, result in report["entries"].items():
        assert "error" not in result, (catalog_id, result)
        assert result["repeat_identical"] is True
        # the device solve ran where the backend says it ran (the CPU, under --allow-cpu)
        assert result["first"]["device"] == "cpu"
        assert result["first"]["finite"] is True

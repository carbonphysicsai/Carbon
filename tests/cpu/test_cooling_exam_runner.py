"""Cooling's sealed-exam runner: the counted run_batch with the graded mesh
family at r = 2√2 and the graded heat-in analysis, nothing else."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "cooling_exam_runner",
    ROOT / "scripts/dev/cold_plate/reference/cooling_exam_runner.py",
)
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)
RR14 = ROOT / "docs/development/evidence/cooling-rr14-20261020/cases"


def _inputs():
    return json.loads((RR14 / "r2s2" / "case.json").read_text())["inputs"]


def test_plans_name_inputs_only():
    good = {"batch": "b", "cases": [{"case_id": "c0", "inputs": _inputs()}]}
    assert runner.check_plan(good) == good["cases"]
    for bad in (
        {"batch": "b", "cases": []},
        {"batch": "b", "cases": [{"case_id": "c", "inputs": _inputs(), "options": {}}]},
        {"batch": "b", "cases": [{"case_id": "a/b", "inputs": _inputs()}]},
        {"batch": "b", "cases": [{"case_id": "c", "inputs": {"inlet_c": 30.0}}]},
    ):
        with pytest.raises(SystemExit):
            runner.check_plan(bad)


def test_every_case_is_the_family_at_r2_root2():
    plan = runner.family_plan(
        {"batch": "b", "cases": [{"case_id": "c", "inputs": _inputs()}]}
    )
    assert plan["cases"][0]["options"] == {
        "mesh_family": "graded-hotspot-v1",
        "resolution": 2 * math.sqrt(2),
    }


def test_the_pinned_image_is_required(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps({"batch": "b", "cases": [{"case_id": "c", "inputs": _inputs()}]})
    )
    monkeypatch.setenv("CARBON_COOLING_IMAGE", "sha256:" + "0" * 64)
    with pytest.raises(SystemExit, match="pinned Cooling image"):
        runner.main([str(plan), "--out", str(tmp_path / "out")])


def test_run_batch_writes_the_family_case_and_judges_with_the_graded_analysis(
    tmp_path, monkeypatch
):
    """The counted run_batch, its docker solve stubbed: the case it writes is
    RR-14's r = 2√2 case byte for byte in its record, and the analysis it
    calls is the graded one."""
    from carbon.cold_plate import analysis, analysis_graded, openfoam
    from scripts.dev.cold_plate.reference import run_batch

    monkeypatch.setenv("CARBON_COOLING_IMAGE", openfoam.IMAGE)
    monkeypatch.setattr(run_batch, "openfoam", run_batch.openfoam)
    monkeypatch.setattr(run_batch, "analysis", run_batch.analysis)
    seen = {}

    def solve(case_dir, name, cpus, timeout_s):
        seen["case"] = json.loads((Path(case_dir) / "case.json").read_text())
        seen["analysis"] = run_batch.analysis
        return "REFERENCE_TIMEOUT", 1.0, "stub"

    monkeypatch.setattr(run_batch, "solve", solve)
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps({"batch": "b", "cases": [{"case_id": "c", "inputs": _inputs()}]})
    )
    runner.main([str(plan), "--out", str(tmp_path / "out"), "--keep", "all"])
    assert seen["case"] == json.loads((RR14 / "r2s2" / "case.json").read_text())
    assert seen["analysis"] is analysis_graded
    record = json.loads(
        (tmp_path / "out" / "records.jsonl").read_text().splitlines()[0]
    )
    assert record["status"] == "REFERENCE_TIMEOUT"
    assert record["options"]["mesh_family"] == "graded-hotspot-v1"
    assert analysis is not analysis_graded

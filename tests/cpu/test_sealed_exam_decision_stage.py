"""The common runner's C5 stage for F02 and F08: thin wrappers over
`sealed_exam_common` (limits and U only), and a stage that reads the sealed
export's reference quantities and the Challenge's registered U."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from carbon.f02 import decision_check as f02
from carbon.f08 import decision_check as f08

REPOSITORY = Path(__file__).resolve().parents[2]
RUNNER = REPOSITORY / "scripts/dev/sealed_exam/run_sealed.sh"


def _stage():
    spec = importlib.util.spec_from_file_location(
        "decision_stage", REPOSITORY / "scripts/dev/sealed_exam/decision_stage.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_f02_labels_beyond_u_of_95_c():
    u = 0.012
    assert f02.label_of({"peak_top_c": 94.0}, u) == "FEASIBLE"
    assert f02.label_of({"peak_top_c": 96.0}, u) == "INFEASIBLE"
    assert f02.label_of({"peak_top_c": 95.005}, u) == "UNRESOLVED"
    assert f02.label_of({"peak_top_c": 94.995}, u) == "UNRESOLVED"


def _cells(key, values):
    return [{"design_id": f"d{i}", key: v} for i, v in enumerate(values)]


def test_f02_needs_a_feasible_and_an_infeasible_design():
    u = 0.012
    assert f02.check(_cells("peak_top_c", [90, 91, 92, 99, 100, 101, 97, 93]), u) is None
    assert f02.check(_cells("peak_top_c", [90.0] * 8), u) == "decision_no_nontrivial_condition"
    assert f02.check(_cells("peak_top_c", [99.0] * 8), u) == "decision_no_nontrivial_condition"
    # every design near the limit: neither side
    assert f02.check(_cells("peak_top_c", [95.001] * 8), u) is not None
    assert f02.check([], u) == "decision_grid_incomplete"


def test_f08_labels_beyond_u_of_the_0_15_limit():
    u = 3.9e-05
    assert f08.label_of({"worst_dynamic_mm_per_n": 0.14}, u) == "FEASIBLE"
    assert f08.label_of({"worst_dynamic_mm_per_n": 0.16}, u) == "INFEASIBLE"
    assert f08.label_of({"worst_dynamic_mm_per_n": 0.15 + 2e-05}, u) == "UNRESOLVED"
    values = [0.13, 0.14, 0.145, 0.155, 0.16, 0.17, 0.12, 0.18]
    assert f08.check(_cells("worst_dynamic_mm_per_n", values), u) is None
    assert f08.check(_cells("worst_dynamic_mm_per_n", [0.12] * 8), u) == "decision_no_nontrivial_condition"


def test_the_stage_reads_the_export_and_the_registered_u():
    stage = _stage()
    u = stage.registered_u("f02", "peak_top_c")
    assert u == 0.012
    peaks = [90.0, 91.0, 92.0, 99.0, 100.0, 101.0, 97.0, 93.0]
    exported = {
        "references": {
            f"c{i}": {"status": "OK", "outputs": {"peak_top_c": p}} for i, p in enumerate(peaks)
        }
    }
    assert stage.decide("f02", exported, u) is None
    exported["references"]["c0"] = {"status": "REFERENCE_SOLVER_FAILED"}
    with pytest.raises(SystemExit):
        stage.decide("f02", exported, u)
    assert stage.registered_u("f08-ribbed-bracket", "worst_dynamic_mm_per_n") == 3.9e-05


def test_the_runner_runs_the_stage_before_qa_and_f02_selects_it():
    text = RUNNER.read_text()
    assert "decision_stage.py" in text
    assert text.index("decision_stage.py") < text.index('"$STATE/$QA_SCRIPT" judge')
    config = (REPOSITORY / "scripts/dev/sealed_exam/configs/f02.env").read_text()
    assert "DECISION_KEY=f02" in config

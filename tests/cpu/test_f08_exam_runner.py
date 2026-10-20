"""F08's reference runner under the family contract: rung decks built as the
exam ladder's (RR-PACKS-07) were, the verified solver build required, and
typed outcomes that keep infrastructure apart from reference failures."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CALCULIX = ROOT / "scripts/dev/reference_packages/calculix"
sys.path.insert(0, str(CALCULIX))
sys.path.insert(0, str(CALCULIX.parent))
_SPEC = importlib.util.spec_from_file_location(
    "f08_exam_runner", CALCULIX / "f08_exam_runner.py"
)
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)
PINS = ROOT / "docs/development/evidence/reference-solvers-2026-10-15/pins"
ACTION = {
    "length_mm": 180.0,
    "width_mm": 75.0,
    "thickness_mm": 8.0,
    "rib_height_mm": 15.0,
    "rib_thickness_mm": 5.0,
    "relief_length_mm": 60.0,
}


def test_the_rungs_and_limits_are_the_ladders():
    import f08_freeze as freeze_mod

    assert runner.RUNGS == (freeze_mod.H_PRIMARY, *freeze_mod.H_WITNESS)
    assert runner.REFERENCE_RUNG == min(runner.RUNGS) == 1.7
    assert runner.MODES == freeze_mod.MODES
    from carbon.f08.domain import INPUTS

    assert runner.INPUTS == INPUTS


def test_mesh_scripts_reproduce_the_pinned_three_rung_decks():
    """The host-independent deck file (make_mesh.py; the others are host
    regenerated) of every rung of the pinned three-rung pilot."""
    import f08_deck as deck

    manifest = json.loads(
        (PINS / "f08-near-feasible-h3-h225-h17-manifest.json").read_text()
    )
    assert len(manifest["cases"]) == 24
    for case in manifest["cases"]:
        h = float(case["case"].split("-h")[1]) if "-h" in case["case"] else 3.0
        assert h in runner.RUNGS
        script = deck.gmsh_script(
            {k: float(case["action"][k]) for k in runner.INPUTS}, h
        )
        digest = hashlib.sha256(script.encode()).hexdigest()
        assert digest == case["files"]["make_mesh.py"]


def test_the_solver_identity_is_the_verified_builds():
    solvers = runner.pinned_solvers()
    assert solvers["kind"] == "calculix"
    assert solvers["solvers"]["ccx"]["sha256"].startswith("21edfdcb")
    assert runner.solvers_id(solvers) == runner.solvers_id()
    other = json.loads(json.dumps(solvers))
    other["solvers"]["ccx"]["sha256"] = "0" * 64
    assert runner.solvers_id(other) != runner.solvers_id(solvers)


def test_a_differing_solver_identity_is_refused(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps({"batch": "b", "cases": [{"case_id": "c", "inputs": ACTION}]})
    )
    monkeypatch.setenv("CARBON_F08_SOLVERS", "sha256:" + "0" * 64)
    with pytest.raises(SystemExit, match="pinned F08 solver identity"):
        runner.main([str(plan), "--out", str(tmp_path / "out")])


def test_plans_are_checked():
    good = {"batch": "b", "cases": [{"case_id": "c0", "inputs": dict(ACTION)}]}
    assert runner.check_plan(good) == good["cases"]
    for bad in (
        {"batch": "b", "cases": []},
        {"batch": "b", "cases": [{"case_id": "a/b", "inputs": dict(ACTION)}]},
        {"batch": "b", "cases": [{"case_id": "c", "inputs": {"length_mm": 180.0}}]},
        {"batch": "b", "cases": [good["cases"][0], good["cases"][0]]},
        {
            "batch": "b",
            "cases": [{"case_id": "c", "inputs": {**ACTION, "length_mm": 181.0}}],
        },
        {
            "batch": "b",
            "cases": [
                {
                    "case_id": "c",
                    "inputs": {**ACTION, "thickness_mm": 8.5},
                }
            ],
        },
    ):
        with pytest.raises(SystemExit):
            runner.check_plan(bad)


def run(stop="exit", code=0):
    return {"stop_reason": stop, "exit": code, "wall_s": 10.0}


def observed(ladder="PASS"):
    return {h: {"mode_ladder": {"verdict": ladder}} for h in runner.RUNGS}


def verdict(asymptotic=True, rung="PASS"):
    return {
        "asymptotic_ok": asymptotic,
        "rungs": {"h3": {"verdict": rung}, "h2.25": {"verdict": "PASS"}},
    }


SOLVED = {h: run() for h in runner.RUNGS}


@pytest.mark.parametrize(
    ("runs", "obs", "ver", "status"),
    [
        (SOLVED, observed(), verdict(), "OK"),
        (SOLVED, observed(), verdict(asymptotic=False), "REFERENCE_INVALID"),
        (SOLVED, observed(), verdict(rung="FAIL"), "REFERENCE_INVALID"),
        (SOLVED, observed(ladder="FAIL"), verdict(), "REFERENCE_INVALID"),
        (SOLVED, {**observed(), 1.7: None}, None, "REFERENCE_SOLVER_FAILED"),
        ({**SOLVED, 2.25: run(code=1)}, observed(), None, "REFERENCE_SOLVER_FAILED"),
        ({**SOLVED, 1.7: run("timeout", 137)}, {}, None, "REFERENCE_TIMEOUT"),
        ({**SOLVED, 1.7: run("memory", 137)}, {}, None, "FAILED_INFRA"),
        ({**SOLVED, 3.0: run("infra", None)}, {}, None, "FAILED_INFRA"),
        ({**SOLVED, 3.0: run(code=137)}, {}, None, "FAILED_INFRA"),
        ({**SOLVED, 3.0: run(code=120)}, {}, None, "FAILED_INFRA"),
    ],
)
def test_outcomes_keep_infrastructure_apart_from_the_reference(runs, obs, ver, status):
    assert runner.classify(runs, obs, ver)[0] == status
    assert (status in runner.TERMINAL) is (status != "FAILED_INFRA")

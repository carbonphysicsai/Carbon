"""M1 E2E U53: a direct campaign's submit read "readback unavailable".

A direct campaign's permitted feedback (Motor, Cooling, the direct versions)
carries its outcome as `result` beside the Ladder (`exam_feedback`) and no
epoch field; the projection read only the Battery shape. It now reads both,
and shows the Ladder as the display rule says: one graded total, A and D as
detail, a gate failure as not eligible.
"""

from __future__ import annotations

import json

from scripts.dev.miner_launchpad import projection

LADDER = {
    "schema": "carbon.private-exam.ladder-feedback.v1",
    "exam_version": "motor-1.3-dev",
    "status": "IMPROVED",
    "total": 0.5488,
    "A": 0.298,
    "D": 0.8,
    "gate_names": [],
}


def _document(exam_feedback):
    return {
        "schema": "carbon.motor.permitted-feedback.v1",
        "challenge": {"id": "electric-motor-magnetics", "version": "1.3"},
        "recipe_digest": "sha256:" + "a" * 64,
        "result": {
            "state": "SCORED",
            "evidence": "DEVELOPMENT",
            "qualification": False,
            "reward": False,
        },
        "exam_feedback": exam_feedback,
    }


def _project(tmp_path, document):
    path = tmp_path / "permitted-final-feedback.json"
    path.write_text(json.dumps(document))
    return projection._validator_outcome(1, path)


def test_a_direct_outcome_is_read_with_its_grade(tmp_path):
    shown = _project(tmp_path, _document({"best": LADDER, "latest": LADDER}))
    assert shown["status"] == "VALIDATOR_OUTCOME"
    assert shown["result"]["state"] == "SCORED"
    grade = shown["result"]["grade"]
    assert grade["latest"] == {
        "status": "IMPROVED",
        "total": 0.5488,
        "A": 0.298,
        "D": 0.8,
        "exam_version": "motor-1.3-dev",
    }
    assert grade["best"]["total"] == 0.5488
    assert "gate_names" not in grade["latest"]


def test_a_direct_outcome_before_any_grade_says_none_yet(tmp_path):
    shown = _project(tmp_path, _document({"best": None, "latest": None}))
    assert shown["result"]["grade"] == {"latest": None, "best": None}


def test_a_battery_shaped_outcome_is_unchanged(tmp_path):
    document = {
        "schema": "carbon.battery.permitted-feedback.v1",
        "epoch": 1,
        "outcome": {"state": "SCORED", "evidence": "DEVELOPMENT"},
    }
    shown = _project(tmp_path, document)
    assert shown["status"] == "VALIDATOR_OUTCOME"
    assert "grade" not in shown["result"]

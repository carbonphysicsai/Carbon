"""Public-shaped replay controls without model rebuild, solver or hidden data."""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from carbon.battery.value import contract as ct
from scripts.dev.score_lab import public_v2_replay as replay
from scripts.dev.score_lab.core import LabRefused

ROOT = Path(__file__).resolve().parents[2]


def _question(qid):
    return {
        "question_id": qid,
        "block_id": qid,
        "fallback_action": "f",
        "actions": {
            "f": [{"status": "FEASIBLE", "objective": 10.0}],
            "a": [{"status": "FEASIBLE", "objective": 2.0}],
            "bad": [{"status": "INFEASIBLE", "objective": 1.0}],
        },
    }


def test_common_mask_never_drops_a_question_for_missing_member_predictions():
    questions = {qid: _question(qid) for qid in ("q1", "q2")}
    prediction = {
        qid: {
            "f": {"feasible": True, "objective": 10.0},
            "a": {"feasible": True, "objective": 2.0},
            "bad": {"feasible": False, "objective": None},
        }
        for qid in questions
    }
    mask = ["q1", "q2"]
    complete = replay.outcomes(questions, prediction, mask, cap=1, kappa=0.1, unit=1)
    assert set(complete) == set(mask)
    missing = {**prediction, "q2": None}
    assert replay.outcomes(questions, missing, mask, cap=1, kappa=0.1, unit=1) is None
    assert mask == ["q1", "q2"]


def test_verified_value_charges_infeasible_attempts_and_abstention_loses_opportunity():
    questions = {"q1": _question("q1"), "q2": _question("q2")}
    risky = {
        qid: {
            "f": {"feasible": True, "objective": 10.0},
            "a": {"feasible": True, "objective": 2.0},
            "bad": {"feasible": True, "objective": 1.0},
        }
        for qid in questions
    }
    one = replay.outcomes(questions, risky, list(questions), cap=1, kappa=0.1, unit=1)
    two = replay.outcomes(questions, risky, list(questions), cap=2, kappa=0.1, unit=1)
    assert one["q1"]["G"] == 0 and one["q1"]["U"] == -0.1
    assert one["q1"]["infeasible_attempts"] == 1
    assert two["q1"]["G"] == 8 and two["q1"]["n"] == 2
    blank = {
        qid: {aid: {"feasible": False, "objective": None} for aid in q["actions"]}
        for qid, q in questions.items()
    }
    abstain = replay.outcomes(
        questions, blank, list(questions), cap=2, kappa=0.1, unit=1
    )
    assert abstain["q1"]["U"] == 0 and abstain["q1"]["missed_opportunity_gain"] == 8
    margin = replay.paired_margin(
        two, one, questions, replicates=20, seed=1, level=0.95
    )
    assert margin["mean_net_margin"] == pytest.approx(7.9)
    assert margin["paired_ci"] == pytest.approx([7.9, 7.9])
    assert margin["questions"] == 2 and margin["blocks"] == 2
    with pytest.raises(LabRefused, match="public_v2_pair_mask_mismatch"):
        replay.paired_margin(
            two, {"q1": one["q1"]}, questions, replicates=20, seed=1, level=0.95
        )


def test_empty_reference_mask_is_insufficient_not_a_zero_margin_win():
    result = replay.paired_margin({}, {}, {}, replicates=20, seed=1, level=0.95)
    assert result == {
        "status": "INSUFFICIENT_EVIDENCE",
        "reason": "NO_ADMITTED_QUESTIONS",
        "questions": 0,
    }
    assert (
        replay.paired_margin(None, {}, {}, replicates=20, seed=1, level=0.95)["status"]
        == "UNMEASURED_MISSING_PREDICTIONS"
    )


def test_existing_cheap_map_never_reads_verification_responses():
    contract = json.loads(
        (ROOT / "carbon/battery/value/contracts/ev4-dev-proof-v1.json").read_bytes()
    )
    refs = {
        job["case_id"]: {
            "status": "OK",
            "outputs": {
                "voltage_v": [4.0] * 10 + [4.2] * 111,
                "temperature_c": [25.0] * 121,
                "plating_margin_v": 0.005,
            },
        }
        for job in ct.decision_cases(contract)
    }
    first, receipt = replay.cheap_predictions(contract, refs)
    changed = copy.deepcopy(refs)
    for job in ct.decision_cases(contract, "verification"):
        changed[job["case_id"]]["outputs"] = {
            "voltage_v": [0.0] * 121,
            "temperature_c": [999.0] * 121,
            "plating_margin_v": -999.0,
        }
    second, receipt2 = replay.cheap_predictions(contract, changed)
    assert first == second and receipt == receipt2
    assert receipt["calibration_cases"] == 420
    assert receipt["verification_response_training"] is False
    assert receipt["primary"] == "bilinear_trace_D"


def test_exact_public_manifest_and_bundle_mutation_control(tmp_path, monkeypatch):
    folder = tmp_path / "public/experiment-predictions"
    folder.mkdir(parents=True)
    lines = []
    for i in range(137):
        name = f"toy{i}-s0.json.gz"
        raw = gzip.compress(json.dumps({"member": f"toy{i}-s0"}).encode(), mtime=0)
        (folder / name).write_bytes(raw)
        lines.append(hashlib.sha256(raw).hexdigest() + "  " + name)
    manifest = tmp_path / replay.MANIFEST
    manifest.parent.mkdir(parents=True)
    body = ("\n".join(lines) + "\n").encode()
    manifest.write_bytes(body)
    monkeypatch.setattr(replay, "ROOT", tmp_path)
    monkeypatch.setattr(replay, "MANIFEST_SHA", hashlib.sha256(body).hexdigest())
    files, pins = replay.inventory(tmp_path / "public")
    assert len(files) == len(pins) == 137
    next(iter(files.values())).write_bytes(b"changed")
    with pytest.raises(LabRefused, match="public_v2_missing_or_changed_bundle"):
        replay.inventory(tmp_path / "public")


def test_absent_q3_and_value_never_become_a_complete_v3_rule():
    rows = {
        m: {
            "eligible": True,
            "E": 0.1,
            "legs": {
                "a": 0.9,
                "r": 0.9,
                "p": 0.9,
                "m": 0.9,
                "n": 0.9,
                "g": 0.9,
                "q": None,
            },
            "gates": {
                "near": 0.0,
                "envelope": 0.0,
                "feasibility": 0.0,
                "plating_fa": 0.0,
                "error": 0.1,
            },
        }
        for m in ("toy1", "toy2")
    }
    result = replay.legacy_report(
        rows,
        {m: {} for m in rows},
        list(rows),
        {m: m for m in rows},
        replicates=5,
        seed=1,
        level=0.95,
    )
    assert result
    assert all(
        row["full_v3_measured"] is False and "tau" not in row for row in result.values()
    )
    q_rules = [row for row in result.values() if "q" in row["missing_required_legs"]]
    assert q_rules and all(
        row["status"] == "UNMEASURED_INCOMPLETE_RULE_INPUTS" for row in q_rules
    )

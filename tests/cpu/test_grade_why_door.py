"""A graded result that does not count says why, through the whole door.

Ship condition 1's caveat: a "does not count" grade named no gate and no
minimum. The receiver already returns the Ladder's closed ``reason`` (and a
leg NAME for a minimum, never a number) and the gate names; these tests carry
a real receiver document through the miner client's own acceptance and the
Launchpad projection, so the page and an agent read the same words.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from test_ladder_store import EXAM, GATES, MOTOR, _intake
from test_launchpad_direct_outcome import _document, _project

from carbon.challenge_validator.ladder_store import LadderStore, checked
from carbon.challenge_validator.ledger import AttemptLedger
from scripts.dev.miner_launchpad import projection

DIGEST = "sha256:" + "a" * 64


@pytest.fixture
def store(tmp_path):
    root = tmp_path / "receiver"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    return LadderStore(AttemptLedger(root / "attempts.sqlite3"))


def _through_the_door(store, graded, tmp_path, leg_minimums=None):
    store.record(
        "5Miner",
        MOTOR,
        EXAM,
        graded,
        exam_version="motor-exam-1",
        gates=GATES,
        rebuild_noise=None,
        recipe_digest=DIGEST,
        epoch=1,
        leg_minimums=leg_minimums,
    )
    body = _intake(store)._feedback("5Miner").body
    ladder = {
        "best": None if body["best"] is None else checked(body["best"]),
        "latest": checked(body["latest"], latest=True),
    }
    shown = _project(tmp_path, _document(ladder))
    return shown["result"]["grade"]


def _graded(status, **more):
    return {
        "artifact_digest": "sha256:" + "a" * 64,
        "status": status,
        "score": 0.4,
        "legs": {"A": 0.1, "D": 0.9},
        "gates": {g: "PASS" for g in GATES},
        **more,
    }


@pytest.mark.parametrize(
    ("graded", "minimums", "reason", "words"),
    [
        (
            _graded("REQUIRED_LEG_MINIMUM_FAILED"),
            {"A": 0.2, "D": 0.2},
            "LEG_MINIMUM_FAILED",
            "not admitted: A below its required minimum",
        ),
        (
            _graded("CANDIDATE_INVALID"),
            None,
            "CANDIDATE_INVALID",
            projection.NOT_SCORED_WORDS["CANDIDATE_INVALID"],
        ),
        (
            _graded("DECISION_OUTCOME_INELIGIBLE"),
            None,
            "DECISION_INELIGIBLE",
            projection.NOT_SCORED_WORDS["DECISION_INELIGIBLE"],
        ),
        (
            _graded("FAILED_INFRA"),
            None,
            "FAILED_INFRA",
            projection.NOT_SCORED_WORDS["FAILED_INFRA"],
        ),
        (
            _graded("INDETERMINATE_EVIDENCE"),
            None,
            "INDETERMINATE",
            projection.NOT_SCORED_WORDS["INDETERMINATE"],
        ),
    ],
)
def test_a_result_that_does_not_count_says_why_at_the_miner_s_door(
    store, tmp_path, graded, minimums, reason, words
):
    grade = _through_the_door(store, graded, tmp_path, minimums)
    latest = grade["latest"]
    assert grade["this_submission"] == "graded"
    assert latest["status"] == "NOT_SCORED"
    assert latest["reason"] == reason and latest["words"] == words
    # Not admitted or not graded, in the Validator's closed words; no total,
    # and nothing but the leg's NAME from the minimum.
    assert words.startswith(("not admitted:", "not graded:"))
    assert "total" not in latest
    assert set(latest) <= {
        "status",
        "words",
        "reason",
        "leg",
        "exam_version",
        "recipe_digest",
        "epoch",
    }
    assert latest.get("leg") in (None, "A")


def test_a_failed_gate_names_the_gate_in_the_words(store, tmp_path):
    graded = _graded(
        "MANDATORY_GATE_FAILED",
        gates={"native_motor_valid": "FAIL", "complete_fixed_coverage": "PASS"},
    )
    latest = _through_the_door(store, graded, tmp_path)["latest"]
    assert latest["status"] == "GATE_FAILED"
    assert latest["gate_names"] == ["native_motor_valid"]
    assert latest["words"] == (
        "graded: not admitted: failed the mandatory gate native motor valid"
    )


def test_the_page_says_why_for_the_miner_s_other_grade_too():
    root = Path(projection.__file__).parent
    for name in ("app.js", "research_view.js"):
        text = (root / name).read_text(encoding="utf-8")
        assert "other.words" in text, name

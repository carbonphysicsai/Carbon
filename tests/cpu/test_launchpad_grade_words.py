"""Every grade the validator can give a submission reads in words (gate round 1, step 2).

F08 1.4's REQUIRED_LEG_MINIMUM_FAILED grade read "not graded yet" on gate1.
The projection maps each Ladder status into words once (`GRADE_WORDS`);
these tests hold that mapping to every scorer verdict on all four launch
Challenges, so a new verdict cannot reach a miner as silence.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from carbon.challenge_validator import exam_cap
from carbon.scoring import dual_score, grade_feedback
from scripts.dev.miner_launchpad import projection

DIGEST = "sha256:" + "ab" * 32
GATES = frozenset({"native_motor_valid", "complete_fixed_coverage"})


def _scorer_verdicts():
    """Every status the dual scorer assigns, read from its source, and every
    outcome the exam cap counts or releases."""
    source = Path(dual_score.__file__).read_text(encoding="utf-8")
    assigned = set(re.findall(r'status = "([A-Z_]+)"', source))
    assert assigned, "the scorer's statuses were not found"
    return sorted(assigned | exam_cap.COUNTED | exam_cap.RELEASED)


def test_every_ladder_status_has_words():
    assert set(projection.GRADE_WORDS) == set(grade_feedback.STATUSES)
    assert all(
        type(text) is str and text.startswith("graded: ")
        for text in projection.GRADE_WORDS.values()
    )


@pytest.mark.parametrize("challenge", exam_cap._LEAN_CHALLENGES)
@pytest.mark.parametrize("verdict", _scorer_verdicts())
def test_every_scorer_verdict_reads_as_graded_in_words(challenge, verdict):
    graded = {"status": verdict, "score": 0.5, "gates": {}}
    if verdict == "MANDATORY_GATE_FAILED":
        graded["gates"] = {"native_motor_valid": "FAIL"}
    document = grade_feedback.ladder_feedback(
        graded,
        best=None,
        exam_version=challenge + "@exam-1",
        gate_registry=GATES,
        rebuild_noise=None,
        recipe_digest=DIGEST,
        epoch=3,
    )
    shown = projection._grade({"latest": document, "best": None}, DIGEST, 3)
    assert shown["this_submission"] == "graded"
    latest = shown["latest"]
    # A NOT_SCORED grade says why when the Ladder carries its closed reason
    # (not admitted / not graded); otherwise the plain words of its status.
    reason = document.get("reason")
    # A leg-minimum failure with no leg name keeps the plain words (the Ladder
    # names the leg or nothing; a number or blank is never shown).
    if reason == "LEG_MINIMUM_FAILED" and not document.get("leg"):
        reason = None
    if document["status"] == "NOT_SCORED" and reason in projection.NOT_SCORED_WORDS:
        assert latest["reason"] == reason
        assert latest["words"].startswith(("not admitted:", "not graded:"))
        assert latest["words"] == projection.NOT_SCORED_WORDS[reason].format(
            leg=document.get("leg")
        )
    elif verdict == "MANDATORY_GATE_FAILED":
        # A failed gate is named in the words (Ship condition 1's caveat).
        assert latest["words"] == (
            "graded: not admitted: failed the mandatory gate native motor valid"
        )
    else:
        assert latest["words"] == projection.GRADE_WORDS[document["status"]]
    if verdict == "MANDATORY_GATE_FAILED":
        assert latest["gate_names"] == ["native_motor_valid"]
    if document["status"] == "NOT_SCORED":
        # A result that does not count reveals no total (Ladder v2/v3).
        assert "total" not in latest


def test_gate_names_are_only_the_ladders_well_formed_names():
    document = {
        "status": "GATE_FAILED",
        "recipe_digest": DIGEST,
        "gate_names": ["ok_gate", "bad gate <b>", 7, "x" * 65],
    }
    shown = projection._grade({"latest": document}, DIGEST)
    assert shown["latest"]["gate_names"] == ["ok_gate"]


def test_the_page_reads_the_mapping_not_its_own_words():
    root = Path(projection.__file__).parent
    for name in ("app.js", "research_view.js"):
        text = (root / name).read_text(encoding="utf-8")
        assert "latest.words" in text, name
        assert "latest.gate_names" in text, name


@pytest.mark.parametrize(
    ("reason", "leg", "words"),
    [
        ("LEG_MINIMUM_FAILED", "A", "not admitted: A below its required minimum"),
        ("CANDIDATE_INVALID", None, projection.NOT_SCORED_WORDS["CANDIDATE_INVALID"]),
        (
            "DECISION_INELIGIBLE",
            None,
            projection.NOT_SCORED_WORDS["DECISION_INELIGIBLE"],
        ),
        ("FAILED_INFRA", None, projection.NOT_SCORED_WORDS["FAILED_INFRA"]),
        ("INDETERMINATE", None, projection.NOT_SCORED_WORDS["INDETERMINATE"]),
    ],
)
def test_a_not_scored_grade_says_why_from_the_ladders_closed_reason(reason, leg, words):
    document = {
        "status": "NOT_SCORED",
        "recipe_digest": DIGEST,
        "reason": reason,
        "leg": leg,
    }
    latest = projection._grade({"latest": document}, DIGEST)["latest"]
    assert latest["words"] == words and latest["reason"] == reason
    assert "total" not in latest
    # A scientific refusal never reads as infrastructure (Validator, invariant 7).
    if reason in ("LEG_MINIMUM_FAILED", "CANDIDATE_INVALID", "DECISION_INELIGIBLE"):
        assert "infrastructure" not in words and "allowance" not in words


def test_an_unknown_reason_or_a_malformed_leg_keeps_the_plain_not_scored_words():
    plain = projection.GRADE_WORDS["NOT_SCORED"]
    for extra in (
        {"reason": "SOMETHING_NEW"},
        {"reason": "LEG_MINIMUM_FAILED", "leg": "0.31"},
        {"reason": "LEG_MINIMUM_FAILED", "leg": None},
    ):
        document = {"status": "NOT_SCORED", "recipe_digest": DIGEST, **extra}
        latest = projection._grade({"latest": document}, DIGEST)["latest"]
        assert latest["words"] == plain and "reason" not in latest
    gated = {"status": "GATE_FAILED", "recipe_digest": DIGEST, "reason": "FAILED_INFRA"}
    assert "reason" not in projection._grade({"latest": gated}, DIGEST)["latest"]

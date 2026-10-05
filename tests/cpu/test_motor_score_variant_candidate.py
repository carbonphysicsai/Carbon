"""Motor's unregistered DEVELOPMENT candidate must remain non-authoritative."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from carbon.motor.score_variant import (
    CandidateInputError,
    candidate_digest,
    candidate_document,
    public_baseline_report,
    score_summary,
)

ROOT = Path(__file__).resolve().parents[2]


def _summary(**changes):
    summary = {
        "n_cases": 30,
        "n_scored": 30,
        "n_gate_failed": 0,
        "n_reference_invalid": 0,
        "n_failed_infra": 0,
        "eligible": True,
        "score": 0.17,
    }
    summary.update(changes)
    return summary


def test_candidate_identity_and_non_authority():
    document = candidate_document()
    assert document["status"] == "CANDIDATE_NOT_ADOPTED"
    assert document["adoption"] == "HUMAN_INPUT"
    assert document["physics_metric"] == "HUMAN_INPUT"
    assert document["promotion_rule"] == "HUMAN_INPUT"
    assert document["source"] == "DEVELOPMENT_PUBLIC_ADAPTIVE"
    assert document["implementation"]["exam_sha256"].startswith("sha256:")
    assert document["implementation"]["candidate_sha256"].startswith("sha256:")
    assert len(candidate_digest()) == 71
    note = (
        ROOT / "docs/development/evidence/motor-score-variant-candidate-v1/README.md"
    ).read_text()
    assert candidate_digest() in note
    scored = score_summary(_summary())
    assert scored["candidate_digest"] == candidate_digest()
    assert scored["official_eligible"] is False
    assert scored["promotable"] is False


def test_unit_interval_and_raw_order_preserved():
    values = [score_summary(_summary(score=e))["score"] for e in (0.0, 0.17, 1.7)]
    assert values == pytest.approx([1.0, 0.5, 1.0 / 11.0])
    assert values[0] > values[1] > values[2]


def test_complete_gate_failure_zero_but_not_authoritative():
    result = score_summary(_summary(n_scored=29, n_gate_failed=1, eligible=False))
    assert result["state"] == "INADMISSIBLE_GATE"
    assert result["known_gate_failure"] is True
    assert result["score"] == 0.0
    assert result["official_eligible"] is False


@pytest.mark.parametrize(
    "changes",
    [
        {"n_cases": 29, "n_scored": 29},
        {"n_scored": 29, "n_reference_invalid": 1},
        {"n_scored": 29, "n_failed_infra": 1},
        {"n_scored": 28, "n_gate_failed": 1, "n_failed_infra": 1, "eligible": False},
    ],
)
def test_unavailable_evidence_stays_nonnumeric(changes):
    result = score_summary(_summary(**changes))
    assert result["state"] == "UNRESOLVED_EVIDENCE"
    assert result["score"] is None
    assert not result["promotable"]
    if changes.get("n_gate_failed"):
        assert result["known_gate_failure"] is True


@pytest.mark.parametrize(
    "changes",
    [
        {"n_cases": True},
        {"n_scored": -1},
        {"n_scored": 31},
        {"eligible": 1},
        {"eligible": False},
        {"score": None},
        {"score": -0.1},
        {"score": math.nan},
        {"score": math.inf},
        {"score": "0.17"},
    ],
)
def test_bad_aggregate_is_refused(changes):
    with pytest.raises(CandidateInputError):
        score_summary(_summary(**changes))


def test_public_baselines_only():
    report = public_baseline_report(ROOT)
    assert set(report["baselines"]) == {"learned", "closed_form"}
    assert report["baselines"]["learned"]["raw_error"] == pytest.approx(
        0.17300702981329621
    )
    assert report["baselines"]["closed_form"]["raw_error"] == pytest.approx(
        0.5002085857247547
    )
    assert (
        report["baselines"]["learned"]["candidate"]["score"]
        > report["baselines"]["closed_form"]["candidate"]["score"]
    )
    assert report["ranking_preserved"] is True
    assert "no promotion" in report["interpretation"]

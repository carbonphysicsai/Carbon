"""Unregistered Cooling [0, 1] DEVELOPMENT score candidate.

This is a monotone presentation transform of the existing public-practice
exam, not a Score Pack, protected evaluation, promotion rule, or miner-facing
scoring path. The science owner has not adopted its scale.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from . import exam
from .challenge import (
    CALIBRATION_SHA256,
    CHALLENGE,
    PRACTICE_CASES,
    PRACTICE_SHA256,
    TRAIN_SHA256,
    PublicMaterial,
)

CANDIDATE_SCHEMA = "carbon.cold-plate.development-score-candidate.v1"
RESULT_SCHEMA = "carbon.cold-plate.development-score-candidate-result.v1"
PROPOSED_SCALE = 0.1


class CandidateInputError(ValueError):
    """The purported base-exam aggregate is inconsistent or malformed."""


def _file_digest(path):
    body = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def candidate_document():
    """The fixed, not-adopted candidate and its public-data provenance."""

    return {
        "schema": CANDIDATE_SCHEMA,
        "id": "cooling-reciprocal-error-candidate-v1",
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "base_rule": "cold-plate-public-practice-v1",
        "implementation": {
            "exam_sha256": _file_digest(exam.__file__),
            "candidate_sha256": _file_digest(__file__),
        },
        "source": "DEVELOPMENT_PUBLIC_ADAPTIVE",
        "material": {
            "train_sha256": "sha256:" + TRAIN_SHA256,
            "practice_sha256": "sha256:" + PRACTICE_SHA256,
            "calibration_sha256": "sha256:" + CALIBRATION_SHA256,
        },
        "transform": {"operator": "reciprocal_error", "scale": PROPOSED_SCALE},
        "scale_basis": "rounded public learned PRACTICE mean error 0.09876205614850035",
        "status": "CANDIDATE_NOT_ADOPTED",
        "adoption": "HUMAN_INPUT",
        "physics_metric": "HUMAN_INPUT",
        "promotion_rule": "HUMAN_INPUT",
    }


def candidate_digest():
    encoded = json.dumps(
        candidate_document(), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _count(summary, key):
    value = summary.get(key)
    if type(value) is not int or value < 0:
        raise CandidateInputError("invalid_" + key)
    return value


def score_summary(summary):
    """Classify one trusted, complete public exam aggregate, never a miner metric.

    The result is deliberately never authoritative. Callers must not use this
    function to score protected evidence; that path belongs to the validator.
    """

    if type(summary) is not dict:
        raise CandidateInputError("aggregate_not_object")
    n_cases = _count(summary, "n_cases")
    n_scored = _count(summary, "n_scored")
    n_gates = _count(summary, "n_gate_failed")
    n_reference = _count(summary, "n_reference_invalid")
    n_infra = _count(summary, "n_failed_infra")
    if n_scored + n_gates + n_reference + n_infra != n_cases:
        raise CandidateInputError("aggregate_counts_inconsistent")
    eligible = summary.get("eligible")
    if type(eligible) is not bool:
        raise CandidateInputError("aggregate_eligibility_malformed")
    if eligible != (n_gates == 0 and n_scored > 0):
        raise CandidateInputError("aggregate_eligibility_inconsistent")

    result = {
        "schema": RESULT_SCHEMA,
        "candidate_digest": candidate_digest(),
        "evidence": "DEVELOPMENT_PUBLIC_ADAPTIVE",
        "official_eligible": False,
        "promotable": False,
        "known_gate_failure": bool(n_gates),
        "score": None,
    }
    if n_cases != PRACTICE_CASES or n_reference or n_infra:
        return {**result, "state": "UNRESOLVED_EVIDENCE"}
    if n_gates:
        return {**result, "state": "INADMISSIBLE_GATE", "score": 0.0}
    if n_scored != PRACTICE_CASES:
        return {**result, "state": "UNRESOLVED_EVIDENCE"}
    error = summary.get("score")
    if type(error) is not float or not math.isfinite(error) or error < 0.0:
        raise CandidateInputError("aggregate_error_malformed")
    score = 1.0 / (1.0 + error / PROPOSED_SCALE)
    if not math.isfinite(score) or not 0.0 < score <= 1.0:
        raise CandidateInputError("candidate_score_invalid")
    return {**result, "state": "CANDIDATE_SCORED", "score": score}


def public_baseline_report(root: str | Path = "."):
    """Measure only the two registered public PRACTICE baseline summaries."""

    calibration = PublicMaterial.load(root).calibration
    practice = calibration["scores"]["practice"]
    names = ("closed_form", "learned")
    baselines = {
        name: {
            "raw_error": practice[name]["score"],
            "candidate": score_summary(practice[name]),
        }
        for name in names
    }
    return {
        "candidate": candidate_document(),
        "candidate_digest": candidate_digest(),
        "baselines": baselines,
        "ranking_preserved": (
            (baselines["learned"]["raw_error"] < baselines["closed_form"]["raw_error"])
            == (
                baselines["learned"]["candidate"]["score"]
                > baselines["closed_form"]["candidate"]["score"]
            )
        ),
        "interpretation": "two adaptively visible public baselines; not promotion or score alignment evidence",
    }


__all__ = [
    "CANDIDATE_SCHEMA",
    "PROPOSED_SCALE",
    "CandidateInputError",
    "candidate_digest",
    "candidate_document",
    "public_baseline_report",
    "score_summary",
]


def _main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", default=".", help="repository root with pinned public material"
    )
    args = parser.parse_args()
    print(json.dumps(public_baseline_report(args.root), sort_keys=True, indent=2))


if __name__ == "__main__":
    _main()

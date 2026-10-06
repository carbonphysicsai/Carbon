"""Motor decision-value safety feedback on public PRACTICE (PRACTICE-SAFETY-01).

Computed on the trusted host from the 30 public PRACTICE references
(`challenge.PRACTICE_PATH`, pinned by `PRACTICE_SHA256`) and the worker's
predictions for them. Feedback only: see `carbon.practice_safety_feedback`.

The reference quantities are each record's `derived.mean_nm` and
`ripple_pk_pk_nm`. The model's come from `exam.feasibility` on its predicted
torque curve, the function Track B's `customer_decision.quantities` uses.
Ripple fraction is `ripple_pk_pk / mean` for a positive mean and infinite
otherwise, `customer_decision`'s definition. A prediction or reference that
fails the exam's validity gates is not read.

- **M1. Ripple-fraction false-feasible rate:** reference above the limit,
  model at or below it.
- **M2. Mean-torque false-feasible rate:** reference below the limit, model
  at or above it.
- **M3. Signed mean-torque bias at J >= 10 A/mm2:** mean model minus
  reference `mean_nm`. Positive is optimistic.

Every comparison is exact, with no band (Test Lead ruling, 2026-10-05). With
30 cases each metric carries its counts and says "n = 30".
"""

from __future__ import annotations

import math

from carbon import practice_safety_feedback as ps

from . import exam
from .challenge import CHALLENGE, PRACTICE_CASES, PRACTICE_PATH, PRACTICE_SHA256

#: Where the limits below are copied from: §6 of the synthetic decision
#: study. The metric never opens it (it also holds the study's designs and
#: conditions). A test binds the copy.
STUDY_SOURCE = "docs/development/studies/MOTOR_SYNTHETIC_DECISION_V2.json"
MIN_MEAN_TORQUE_NM = 4.0
MAX_RIPPLE_FRACTION = 0.30
#: M3's current-density floor (the ticket's value).
STRONG_CURRENT_DENSITY_A_MM2 = 10.0
SAMPLE = f"n = {PRACTICE_CASES}"
POSITIVE_IS_OPTIMISTIC = "model minus reference; positive is optimistic"

_RATE_ROW = {
    "false_feasible": ps.COUNT,
    "reference_fail": ps.COUNT,
    "rate": ps.NUMBER,
    "sample": ps.literal(SAMPLE),
    "uncertainty": ps.literal(ps.NO_BAND),
    "feedback_only": ps.TRUE,
}
ALLOWED = {
    "M1": _RATE_ROW,
    "M2": _RATE_ROW,
    "M3": {
        "signed_mean_nm": ps.NUMBER,
        "cases": ps.COUNT,
        "sign": ps.literal(POSITIVE_IS_OPTIMISTIC),
        "sample": ps.literal(SAMPLE),
        "uncertainty": ps.literal(ps.NO_BAND),
        "feedback_only": ps.TRUE,
    },
}


def _valid(outputs):
    if type(outputs) is not dict:
        return False
    return all(v != exam.FAIL for v in exam.gates(outputs).values())


def _fraction(mean, ripple):
    return ripple / mean if mean > 0 else math.inf


def safety(predictions, practice):
    """The allow-listed safety document for one practice result."""
    records = practice.records
    unmeasured = sum(not _valid(predictions.get(r["case_id"])) for r in records)
    ripple = {"false_feasible": 0, "reference_fail": 0}
    torque = {"false_feasible": 0, "reference_fail": 0}
    strong, unresolved = [], 0
    for record in records:
        if record.get("status") != "OK" or not _valid(record["outputs"]):
            unresolved += 2  # both constraints' reference verdicts
            continue
        if unmeasured:
            continue
        ref_mean = float(record["derived"]["mean_nm"])
        ref_fraction = _fraction(ref_mean, float(record["derived"]["ripple_pk_pk_nm"]))
        said = exam.feasibility(
            predictions[record["case_id"]],
            min_torque_nm=MIN_MEAN_TORQUE_NM,
            max_ripple_fraction=MAX_RIPPLE_FRACTION,
        )
        said_fraction = _fraction(said["mean_nm"], said["ripple_pk_pk_nm"])
        if ref_fraction > MAX_RIPPLE_FRACTION:
            ripple["reference_fail"] += 1
            ripple["false_feasible"] += said_fraction <= MAX_RIPPLE_FRACTION
        if ref_mean < MIN_MEAN_TORQUE_NM:
            torque["reference_fail"] += 1
            torque["false_feasible"] += said["mean_nm"] >= MIN_MEAN_TORQUE_NM
        if record["inputs"]["current_density_a_mm2"] >= STRONG_CURRENT_DENSITY_A_MM2:
            strong.append(said["mean_nm"] - ref_mean)

    def rated(row):
        return {
            **row,
            "rate": ps.rate(row["false_feasible"], row["reference_fail"]),
            "sample": SAMPLE,
            "uncertainty": ps.NO_BAND,
            "feedback_only": True,
        }

    metrics = (
        {"M1": None, "M2": None, "M3": None}
        if unmeasured
        else {
            "M1": rated(ripple),
            "M2": rated(torque),
            "M3": {
                "signed_mean_nm": ps.signed_mean(strong),
                "cases": len(strong),
                "sign": POSITIVE_IS_OPTIMISTIC,
                "sample": SAMPLE,
                "uncertainty": ps.NO_BAND,
                "feedback_only": True,
            },
        }
    )
    return ps.document(
        CHALLENGE.challenge_id,
        metrics,
        unmeasured=unmeasured,
        unresolved=unresolved,
        material={"path": PRACTICE_PATH, "sha256": PRACTICE_SHA256},
        allowed=ALLOWED,
    )

"""Cold-plate decision-value safety feedback on public PRACTICE (PRACTICE-SAFETY-01).

Computed on the trusted host from the 100 public PRACTICE references
(`challenge.PRACTICE_PATH`, pinned by `PRACTICE_SHA256`) and the worker's
predictions for them. Feedback only: see `carbon.practice_safety_feedback`.

The decision quantities are `exam.feasibility`'s, the function Track B's
`customer_decision.quantities` uses: the die peak (from `peak_c`, the face
profile and the TIM) and the hydraulic power (pressure drop times flow), at
each practice case's own inputs, for reference and model alike. A prediction
or reference that fails the exam's validity gates is not read, as
`customer_decision.quantities` refuses it.

- **C1. Die-limit false-feasible rate:** reference die peak above the limit,
  model at or below it.
- **C2. Hydraulic-power false-feasible rate:** reference above the limit,
  model at or below it.
- **C3. Signed die-peak error:** mean model minus reference die peak, degC,
  over the cases whose reference die peak is within 10 degC of the limit.

Every comparison is exact, with no band (Test Lead ruling, 2026-10-05), and
every metric says so.
"""

from __future__ import annotations

from carbon import practice_safety_feedback as ps

from . import exam
from .challenge import CHALLENGE, PRACTICE_PATH, PRACTICE_SHA256

#: Where the limits below are copied from: the study's synthetic scenario.
#: The metric never opens it (it also holds the study's designs and
#: conditions). A test binds the copy.
STUDY_SOURCE = "docs/development/studies/AI_ACCELERATOR_COOLING_SYNTHETIC_V1.json"
DIE_LIMIT_C = 100.0
HYDRAULIC_LIMIT_W = 0.25
#: C3's window around the die limit (the ticket's value).
NEAR_DIE_LIMIT_C = 10.0
MODEL_MINUS_REFERENCE = "model minus reference; negative is optimistic"

_RATE_ROW = {
    "false_feasible": ps.COUNT,
    "reference_fail": ps.COUNT,
    "rate": ps.NUMBER,
    "uncertainty": ps.literal(ps.NO_BAND),
    "feedback_only": ps.TRUE,
}
ALLOWED = {
    "C1": _RATE_ROW,
    "C2": _RATE_ROW,
    "C3": {
        "signed_mean_c": ps.NUMBER,
        "cases": ps.COUNT,
        "sign": ps.literal(MODEL_MINUS_REFERENCE),
        "uncertainty": ps.literal(ps.NO_BAND),
        "feedback_only": ps.TRUE,
    },
}


def _valid(outputs, case):
    if type(outputs) is not dict:
        return False
    return all(v != exam.FAIL for v in exam.gates(outputs, case).values())


def _quantities(case, outputs):
    return exam.feasibility(
        case, outputs, die_limit_c=DIE_LIMIT_C, hydraulic_limit_w=HYDRAULIC_LIMIT_W
    )


def safety(predictions, practice):
    """The allow-listed safety document for one practice result."""
    records = practice.records
    unmeasured = sum(
        not _valid(predictions.get(r["case_id"]), r["inputs"]) for r in records
    )
    die = {"false_feasible": 0, "reference_fail": 0}
    hydraulic = {"false_feasible": 0, "reference_fail": 0}
    near, unresolved = [], 0
    for record in records:
        case = record["inputs"]
        if record.get("status") != "OK" or not _valid(record["outputs"], case):
            unresolved += 2  # both constraints' reference verdicts
            continue
        if unmeasured:
            continue
        truth = _quantities(case, record["outputs"])
        said = _quantities(case, predictions[record["case_id"]])
        if truth["die_peak_c"] > DIE_LIMIT_C:
            die["reference_fail"] += 1
            die["false_feasible"] += said["die_peak_c"] <= DIE_LIMIT_C
        if truth["hydraulic_w"] > HYDRAULIC_LIMIT_W:
            hydraulic["reference_fail"] += 1
            hydraulic["false_feasible"] += said["hydraulic_w"] <= HYDRAULIC_LIMIT_W
        if abs(truth["die_peak_c"] - DIE_LIMIT_C) <= NEAR_DIE_LIMIT_C:
            near.append(said["die_peak_c"] - truth["die_peak_c"])

    def rated(row):
        return {
            **row,
            "rate": ps.rate(row["false_feasible"], row["reference_fail"]),
            "uncertainty": ps.NO_BAND,
            "feedback_only": True,
        }

    metrics = (
        {"C1": None, "C2": None, "C3": None}
        if unmeasured
        else {
            "C1": rated(die),
            "C2": rated(hydraulic),
            "C3": {
                "signed_mean_c": ps.signed_mean(near),
                "cases": len(near),
                "sign": MODEL_MINUS_REFERENCE,
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

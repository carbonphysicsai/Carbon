"""Battery decision-value safety feedback on public PRACTICE (PRACTICE-SAFETY-01).

Computed on the trusted host from the 200 public PRACTICE references
(`practice.PracticeSet`, pinned by `PRACTICE_SOURCE_SHA256`) and the worker's
predictions for them. Feedback only: see `carbon.practice_safety_feedback`.

- **B1. Near-limit false acceptance per constraint.** On the published
  important region (`domain.is_important`), the cases the reference resolves
  as FAIL with EV4's bands (`decision.check`), and how many the model calls
  PASS without bands. The worst constraint is named. The same counts as
  `value.false_acceptance.component`.
- **B2. Near-limit optimism.** The mean over the important cases and both
  constraints of how far the model's margin exceeds the reference's, in EV4
  band units: `value.admissibility.near_optimism`, the EV5 gate's measure. The
  value only; the gate's verdict and cutoff are not shown.
- **B3. Signed near-limit margin error.** Per constraint, the mean of
  predicted minus reference margin in band units over the important cases
  (`value.margins._margins`). Positive is optimistic.
- **B4. Feasible-choice rate on the practice decision set.** BLOCKED until
  Data Collection commits the set (`DECISION_SET_PATH` is None).

The value modules named above import the scoring-set module, so this module
reimplements their few lines over `value.decision` alone; a test proves the
results identical on the practice references.
"""

from __future__ import annotations

import math

from carbon import practice_safety_feedback as ps

from .challenge import CHALLENGE
from .domain import GRID_POINTS, is_important
from .practice import PRACTICE_SOURCE_PATH, PRACTICE_SOURCE_SHA256
from .value import decision as d

#: Where EV4's decision rules below are copied from. The metric never opens
#: it: the contract also holds EV4's conditions. A test binds the copy.
CONTRACT_SOURCE = "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
#: EV4's objective, constraints and reference bands, as `decision.measure`
#: and `decision.check` read them, and nothing else of the contract.
DECISION_RULES = {
    "objective": {"threshold_v": 4.19, "charge_start_s": 120.0, "window_s": 3600.0},
    "constraints": [
        {"id": "reach_cv_in_window"},
        {"id": "no_plating_onset", "threshold": 0.0},
        {"id": "peak_temperature", "threshold": 45.0},
    ],
    "reference": {
        "uncertainty": {
            "bands": {
                "time_to_cv_onset_s": 3.15,
                "plating_margin_v": 0.00197,
                "peak_temperature_c": 0.157,
            }
        }
    },
}
CONSTRAINTS = ("no_plating_onset", "peak_temperature")
#: The committed practice decision set for B4. None until Data Collection
#: commits it; B4 reports BLOCKED meanwhile and nothing is fabricated.
DECISION_SET_PATH = None
#: The ruled minimum distance of a practice decision condition from every
#: EV1/EV2/EV4/EV5 condition and protected grid (Test Lead, 2026-10-05).
DECISION_SET_MIN_T_AMB_C = 2.0
DECISION_SET_MIN_SOC0 = 0.03
POSITIVE_IS_OPTIMISTIC = "predicted minus reference; positive is optimistic"

_RATE_ROW = {
    "false_acceptance": ps.COUNT,
    "reference_fail": ps.COUNT,
    "rate": ps.NUMBER,
}
_SIGNED_ROW = {"signed_mean_bands": ps.NUMBER, "cases": ps.COUNT}
ALLOWED = {
    "B1": {
        **{c: _RATE_ROW for c in CONSTRAINTS},
        "worst": ps.literal(None, *CONSTRAINTS),
        "feedback_only": ps.TRUE,
    },
    "B2": {"near_optimism_bands": ps.NUMBER, "feedback_only": ps.TRUE},
    "B3": {
        **{c: _SIGNED_ROW for c in CONSTRAINTS},
        "sign": ps.literal(POSITIVE_IS_OPTIMISTIC),
        "feedback_only": ps.TRUE,
    },
    "B4": ps.literal(ps.B4_BLOCKED),
}


def _finite_series(value):
    return (
        type(value) in (list, tuple)
        and len(value) == GRID_POINTS
        and all(_finite(v) for v in value)
    )


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measurable(outputs):
    """Whether a prediction carries every output the metrics read, finite and
    of its declared shape. Anything else is UNMEASURED, never clean."""
    return (
        type(outputs) is dict
        and _finite_series(outputs.get("voltage_v"))
        and _finite_series(outputs.get("temperature_c"))
        and _finite(outputs.get("plating_margin_v"))
    )


def margins(outputs):
    """Signed margins (positive is safe) in EV4 band units
    (`value.margins._margins` over `DECISION_RULES`)."""
    rules = {c["id"]: c for c in DECISION_RULES["constraints"]}
    bands = DECISION_RULES["reference"]["uncertainty"]["bands"]
    q = d.measure(DECISION_RULES, outputs)
    return {
        "no_plating_onset": (
            q["plating_margin_v"] - rules["no_plating_onset"]["threshold"]
        )
        / bands["plating_margin_v"],
        "peak_temperature": (
            rules["peak_temperature"]["threshold"] - q["peak_temperature_c"]
        )
        / bands["peak_temperature_c"],
    }


def near_case_ids(practice):
    """The practice cases in the published important region."""
    return [r["case_id"] for r in practice.records if is_important(r)]


def safety(predictions, practice):
    """The allow-listed safety document for one practice result."""
    refs = {r["case_id"]: r for r in practice.records}
    unmeasured = sum(not measurable(predictions.get(c)) for c in refs)
    near = near_case_ids(practice)
    counts = {c: {"false_acceptance": 0, "reference_fail": 0} for c in CONSTRAINTS}
    unresolved = 0
    optimism, signed = [], {c: [] for c in CONSTRAINTS}
    bands = DECISION_RULES["reference"]["uncertainty"]["bands"]
    for case_id in near:
        reference = refs[case_id]["outputs"]
        truth = d.check(DECISION_RULES, d.measure(DECISION_RULES, reference), bands)
        for constraint in CONSTRAINTS:
            unresolved += truth[constraint] == d.UNRESOLVED
        if unmeasured:
            continue
        outputs = predictions[case_id]
        said = d.check(DECISION_RULES, d.measure(DECISION_RULES, outputs))
        said_m, truth_m = margins(outputs), margins(reference)
        for constraint in CONSTRAINTS:
            if truth[constraint] == d.FAIL:
                counts[constraint]["reference_fail"] += 1
                counts[constraint]["false_acceptance"] += said[constraint] == d.PASS
            delta = said_m[constraint] - truth_m[constraint]
            optimism.append(max(0.0, delta))
            signed[constraint].append(delta)
    if unmeasured:
        b1 = b2 = b3 = None
    else:
        rows = {
            c: {
                **counts[c],
                "rate": ps.rate(
                    counts[c]["false_acceptance"], counts[c]["reference_fail"]
                ),
            }
            for c in CONSTRAINTS
        }
        rated = {c: rows[c]["rate"] for c in CONSTRAINTS if rows[c]["rate"] is not None}
        b1 = {
            **rows,
            "worst": max(rated, key=lambda c: (rated[c], c)) if rated else None,
            "feedback_only": True,
        }
        b2 = {"near_optimism_bands": ps.signed_mean(optimism), "feedback_only": True}
        b3 = {
            **{
                c: {
                    "signed_mean_bands": ps.signed_mean(signed[c]),
                    "cases": len(signed[c]),
                }
                for c in CONSTRAINTS
            },
            "sign": POSITIVE_IS_OPTIMISTIC,
            "feedback_only": True,
        }
    return ps.document(
        CHALLENGE.challenge_id,
        {"B1": b1, "B2": b2, "B3": b3, "B4": ps.B4_BLOCKED},
        unmeasured=unmeasured,
        unresolved=unresolved,
        material={"path": PRACTICE_SOURCE_PATH, "sha256": PRACTICE_SOURCE_SHA256},
        allowed=ALLOWED,
    )


def decision_set_clear(conditions, protected):
    """Whether every practice decision condition `(t_amb_c, soc0)` lies at
    least the ruled distance from every protected condition (`_clear`)."""
    return all(_clear(c, p) for c in conditions for p in protected)


def _clear(condition, protected):
    """The ruled separation as written: at least 2 degC in t_amb AND at least
    0.03 in soc0 from the protected condition. This literal reading is the
    stricter one, so it fails closed; whether the ruling meant an exclusion
    box (either coordinate far enough) is an open Test Lead question."""
    return (
        abs(condition[0] - protected[0]) >= DECISION_SET_MIN_T_AMB_C
        and abs(condition[1] - protected[1]) >= DECISION_SET_MIN_SOC0
    )

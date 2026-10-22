"""The Battery sealed grid's post-solve checks (OWNER-BATTERY-EXAM-GRID-01;
VALIDATOR_BATTERY_SEALED_RULINGS_20261022 section 11 rules 4 and 5): a thin
wrapper over `sealed_exam_common` (VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022,
C5 and C6) that supplies only Battery's quantity and U.

On the **reference** v2 labels (never the placement predictions), with the
registered plating U (`battery-reference-uncertainty.json`, 0.00023 V on the
mesh-160 margin):

- a case is on a side (FEASIBLE or INFEASIBLE) only when its v2 label is that
  side and its mesh-160 margin is more than U from 0; an UNRESOLVED label or a
  margin within U of 0 is on neither side;
- **straddle** (C6): at least one third of all 140 cases on each side;
- **decision check** (C5, selection rule PER_CONDITION: each scenario picks its
  own candidate): every scenario has at least one candidate FEASIBLE beyond U
  (else the registered `q3_judge_v2` returns None and the scenario drops out of
  D) and at least one INFEASIBLE beyond U (a non-trivial choice).

A failed check makes the batch unusable (one redraw, then STOP).
"""

from __future__ import annotations

from carbon.challenge_validator import sealed_exam_common as common

FEASIBLE, INFEASIBLE = common.FEASIBLE, common.INFEASIBLE
LIMIT = "plating_margin_m160_v"


def side(label, m160_v, u_v):
    """FEASIBLE, INFEASIBLE or None (neither) for one case."""
    if label not in (FEASIBLE, INFEASIBLE) or abs(m160_v) <= u_v:
        return None
    return label


def straddle(cases, u_v):
    """None when each side holds at least a third of `cases`, else a failure kind.

    `cases` is a list of `{scenario_id, label, m160_v}`."""
    return common.straddle({LIMIT: [side(c["label"], c["m160_v"], u_v) for c in cases]})


def decision(cases, u_v):
    """None when every scenario has a FEASIBLE and an INFEASIBLE candidate beyond
    U, else a failure kind. A candidate is a cell of its scenario (condition)."""
    cells = [
        {
            "design_id": f"candidate-{i}",
            "condition_id": c["scenario_id"],
            "side": side(c["label"], c["m160_v"], u_v),
        }
        for i, c in enumerate(cases)
    ]
    # the cases of one scenario are its candidates; a design id repeats across
    # scenarios only through the position within the scenario
    seen = {}
    for cell in cells:
        k = seen.get(cell["condition_id"], 0)
        seen[cell["condition_id"]] = k + 1
        cell["design_id"] = f"candidate-{k}"
    return common.decision_check(
        cells,
        lambda c: c["side"] or common.UNRESOLVED,
        choice=common.PER_CONDITION,
    )


__all__ = ["FEASIBLE", "INFEASIBLE", "decision", "side", "straddle"]

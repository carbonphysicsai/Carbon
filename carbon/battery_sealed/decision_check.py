"""The Battery sealed grid's post-solve checks (OWNER-BATTERY-EXAM-GRID-01;
VALIDATOR_BATTERY_SEALED_RULINGS_20261022 §11 rules 4 and 5).

On the **reference** v2 labels (never the placement predictions), with the
registered plating U (`battery-reference-uncertainty.json`, 0.00023 V on the
mesh-160 margin):

- a case is on a side (FEASIBLE or INFEASIBLE) only when its v2 label is that
  side and its mesh-160 margin is more than U from 0; an UNRESOLVED label or a
  margin within U of 0 is on neither side;
- **straddle** (rule 5): at least one third of all 140 cases on each side;
- **decision check** (rule 4): every scenario has at least one candidate
  FEASIBLE beyond U (else the registered `q3_judge_v2` returns None and the
  scenario drops out of D) and at least one INFEASIBLE beyond U (a non-trivial
  choice).

A failed check makes the batch unusable (one redraw, then STOP).
"""

from __future__ import annotations

FEASIBLE, INFEASIBLE = "FEASIBLE", "INFEASIBLE"


def side(label, m160_v, u_v):
    """FEASIBLE, INFEASIBLE or None (neither) for one case."""
    if label not in (FEASIBLE, INFEASIBLE) or abs(m160_v) <= u_v:
        return None
    return label


def straddle(cases, u_v):
    """None when each side holds at least a third of `cases`, else a failure kind.

    `cases` is a list of `{scenario_id, label, m160_v}`."""
    sides = [side(c["label"], c["m160_v"], u_v) for c in cases]
    third = len(cases) / 3
    if sides.count(FEASIBLE) < third or sides.count(INFEASIBLE) < third:
        return "straddle_short:plating_margin_m160_v"
    return None


def decision(cases, u_v):
    """None when every scenario has a FEASIBLE and an INFEASIBLE candidate
    beyond U, else a failure kind."""
    scenarios = sorted({c["scenario_id"] for c in cases})
    for scenario in scenarios:
        sides = {
            side(c["label"], c["m160_v"], u_v)
            for c in cases
            if c["scenario_id"] == scenario
        }
        if FEASIBLE not in sides:
            return "decision_scenario_no_feasible"
        if INFEASIBLE not in sides:
            return "decision_scenario_no_infeasible"
    return None


__all__ = ["FEASIBLE", "INFEASIBLE", "decision", "side", "straddle"]

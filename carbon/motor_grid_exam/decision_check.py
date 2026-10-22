"""The sealed grid's post-solve decision check (VALIDATOR_RULING_MOTOR_GRID_SPLIT_20261022).

On the **reference** labels (never the placement predictions) a sealed grid must
be able to measure design value: the decision contract must evaluate without
error, at least one condition must have a non-trivial choice (both a feasible
and an infeasible design) and at least one design must be feasible at every
condition. Otherwise the batch is unusable, exactly like a straddle shortfall
(one redraw, then STOP).

A cell's reference label is FEASIBLE when both limits hold by more than the
registered U (mean torque >= 4.0 N.m, ripple fraction <= 0.30), INFEASIBLE when
a limit is violated by more than U, and UNRESOLVED (neither) otherwise. The
selection rule is the contract's (`customer_decision.TIE_POLICY`): among designs
feasible at every condition, the lowest worst-case ripple fraction; ties by the
higher worst-condition mean torque, then the lower design id.
"""

from __future__ import annotations

import math

from .domain import MAX_RIPPLE_FRACTION, MIN_TORQUE_NM

FEASIBLE, INFEASIBLE, UNRESOLVED = "FEASIBLE", "INFEASIBLE", "UNRESOLVED"


def label(mean_torque_nm, ripple_fraction, u_torque, u_ripple):
    """One cell's reference label under the registered U."""
    if not (math.isfinite(mean_torque_nm) and math.isfinite(ripple_fraction)):
        raise ValueError("a reference quantity is not finite")
    torque_margin = mean_torque_nm - MIN_TORQUE_NM
    ripple_margin = MAX_RIPPLE_FRACTION - ripple_fraction
    if torque_margin < -u_torque or ripple_margin < -u_ripple:
        return INFEASIBLE
    if torque_margin > u_torque and ripple_margin > u_ripple:
        return FEASIBLE
    return UNRESOLVED


def check(cells, u_torque, u_ripple):
    """`None` when the grid can measure design value, else a failure kind.

    `cells` is a list of `{design_id, condition_id, mean_torque_nm,
    ripple_fraction}` for the 5 x 6 grid."""
    designs = sorted({c["design_id"] for c in cells})
    conditions = sorted({c["condition_id"] for c in cells})
    labels = {
        (c["design_id"], c["condition_id"]): label(
            c["mean_torque_nm"], c["ripple_fraction"], u_torque, u_ripple
        )
        for c in cells
    }
    if len(labels) != len(cells) or len(labels) != len(designs) * len(conditions):
        return "decision_grid_incomplete"
    nontrivial = [
        k
        for k in conditions
        if {labels[(d, k)] for d in designs} >= {FEASIBLE, INFEASIBLE}
    ]
    everywhere = [
        d for d in designs if all(labels[(d, k)] == FEASIBLE for k in conditions)
    ]
    if not nontrivial:
        return "decision_no_nontrivial_condition"
    if not everywhere:
        return "decision_no_design_feasible_everywhere"
    by_cell = {(c["design_id"], c["condition_id"]): c for c in cells}

    def key(d):
        worst_ripple = max(by_cell[(d, k)]["ripple_fraction"] for k in conditions)
        worst_torque = min(by_cell[(d, k)]["mean_torque_nm"] for k in conditions)
        return (worst_ripple, -worst_torque, d)

    if not math.isfinite(key(min(everywhere, key=key))[0]):
        return "decision_contract_error"
    return None


__all__ = ["FEASIBLE", "INFEASIBLE", "UNRESOLVED", "check", "label"]

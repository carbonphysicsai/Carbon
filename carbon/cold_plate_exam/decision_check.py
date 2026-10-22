"""The Cooling sealed grid's post-solve decision check (Validator, 2026-10-22).

On the **reference** quantities (never the placement predictions) a sealed 4 x 4
grid must be gradable as a design decision: at least one design must be
FEASIBLE, beyond the registered U, at all 4 conditions. Otherwise the batch is
unusable (one redraw, then STOP), and Cooling's grading would refuse it
(`cooling_no_feasible_reference`).

A cell is FEASIBLE when both limits hold by more than the registered U (die peak
<= 100 C by more than 0.037 C; hydraulic power <= 0.25 W by more than 3 percent
relative to the cell's value, the QA's own rule), INFEASIBLE when a limit is
violated by more than U, and UNRESOLVED (neither) otherwise.
"""

from __future__ import annotations

import math

from .domain import DIE_LIMIT_C, HYDRAULIC_LIMIT_W

FEASIBLE, INFEASIBLE, UNRESOLVED = "FEASIBLE", "INFEASIBLE", "UNRESOLVED"


def label(die_peak_c, hydraulic_w, u_die_c, u_hydraulic_relative):
    """One cell's reference label under the registered U."""
    if not (math.isfinite(die_peak_c) and math.isfinite(hydraulic_w)):
        raise ValueError("a reference quantity is not finite")
    die_margin = DIE_LIMIT_C - die_peak_c
    hydraulic_margin = HYDRAULIC_LIMIT_W - hydraulic_w
    u_hydraulic = u_hydraulic_relative * abs(hydraulic_w)
    if die_margin < -u_die_c or hydraulic_margin < -u_hydraulic:
        return INFEASIBLE
    if die_margin > u_die_c and hydraulic_margin > u_hydraulic:
        return FEASIBLE
    return UNRESOLVED


def check(cells, u_die_c, u_hydraulic_relative):
    """`None` when some design is FEASIBLE at every condition, else a failure kind.

    `cells` is a list of `{design_id, condition_id, die_peak_c, hydraulic_w}`
    for the 4 x 4 grid."""
    designs = sorted({c["design_id"] for c in cells})
    conditions = sorted({c["condition_id"] for c in cells})
    labels = {
        (c["design_id"], c["condition_id"]): label(
            c["die_peak_c"], c["hydraulic_w"], u_die_c, u_hydraulic_relative
        )
        for c in cells
    }
    if len(labels) != len(cells) or len(labels) != len(designs) * len(conditions):
        return "decision_grid_incomplete"
    if not any(all(labels[(d, k)] == FEASIBLE for k in conditions) for d in designs):
        return "decision_no_feasible_design"
    return None


__all__ = ["FEASIBLE", "INFEASIBLE", "UNRESOLVED", "check", "label"]

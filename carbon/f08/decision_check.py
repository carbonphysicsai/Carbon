"""F08's sealed-grid decision check (C5, VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022):
a thin wrapper over `sealed_exam_common`, supplying only F08's limit and U.

F08 is a one-condition grid whose cases are the designs: a cell is FEASIBLE when
the worst dynamic compliance at the reference rung (h = 1.7 mm) is under
0.15 mm/N by more than U (the registered reference uncertainty), INFEASIBLE when
over it by more than U, else UNRESOLVED. The batch needs a FEASIBLE and an
INFEASIBLE design and a design FEASIBLE at the condition (selection rule ROBUST).
"""

from __future__ import annotations

from carbon.challenge_validator import sealed_exam_common as common

from .domain import LIMIT_MM_PER_N

QUANTITY = "worst_dynamic_mm_per_n"
CONDITION_ID = "condition-0"


def label_of(cell, u):
    return common.label_value([(cell[QUANTITY], LIMIT_MM_PER_N, "<=", u)])


def check(cells, u):
    """`None` when the batch can measure design value, else a closed failure kind.

    `cells`: `{design_id, worst_dynamic_mm_per_n}` per case (one condition)."""
    full = [{**c, "condition_id": CONDITION_ID} for c in cells]
    return common.decision_check(
        full, lambda c: label_of(c, u), choice=common.ROBUST
    )


__all__ = ["check", "label_of"]

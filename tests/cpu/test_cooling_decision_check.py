"""Cooling's sealed-grid post-solve decision check (Validator, 2026-10-22): a
batch with no design FEASIBLE beyond U at all four conditions is unusable."""

from __future__ import annotations

import pytest

from carbon.cold_plate_exam import decision_check as dc

U_DIE, U_HYD = 0.037, 0.03


def cells(feasible, die_ok=80.0, hyd_ok=0.1):
    out = []
    for d in range(4):
        for c in range(4):
            ok = feasible(d, c)
            out.append(
                {
                    "design_id": f"d{d + 1}",
                    "condition_id": f"c{c + 1}",
                    "die_peak_c": die_ok if ok else 120.0,
                    "hydraulic_w": hyd_ok if ok else 0.5,
                }
            )
    return out


def test_a_grid_with_a_design_feasible_at_every_condition_passes():
    assert dc.check(cells(lambda d, c: d == 0 or c < 2), U_DIE, U_HYD) is None


def test_a_grid_with_no_such_design_is_refused():
    # every design fails at one condition (a different one each)
    assert dc.check(cells(lambda d, c: c != d), U_DIE, U_HYD) == "decision_no_feasible_design"
    # nothing feasible at all
    assert dc.check(cells(lambda d, c: False), U_DIE, U_HYD) == "decision_no_feasible_design"


def test_an_incomplete_grid_is_refused():
    assert dc.check(cells(lambda d, c: True)[:15], U_DIE, U_HYD) == "decision_grid_incomplete"


def test_cells_within_u_of_a_limit_are_unresolved_not_feasible():
    # 0.01 C under the die limit (U 0.037) and 1 percent under the hydraulic limit (U 3 percent)
    assert dc.label(99.99, 0.1, U_DIE, U_HYD) == dc.UNRESOLVED
    assert dc.label(80.0, 0.248, U_DIE, U_HYD) == dc.UNRESOLVED
    assert dc.label(80.0, 0.1, U_DIE, U_HYD) == dc.FEASIBLE
    assert dc.label(100.5, 0.1, U_DIE, U_HYD) == dc.INFEASIBLE
    assert dc.label(80.0, 0.3, U_DIE, U_HYD) == dc.INFEASIBLE
    # a design only UNRESOLVED at one condition does not count as feasible there
    near = cells(lambda d, c: True)
    near[0] = {**near[0], "die_peak_c": 99.99}
    assert dc.check([c for c in near if c["design_id"] == "d1"] + [
        {**c, "die_peak_c": 120.0} for c in near if c["design_id"] != "d1"
    ], U_DIE, U_HYD) == "decision_no_feasible_design"


def test_a_non_finite_reference_quantity_is_an_error():
    with pytest.raises(ValueError):
        dc.label(float("nan"), 0.1, U_DIE, U_HYD)

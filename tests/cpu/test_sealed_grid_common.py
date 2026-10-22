"""The sealed graders' shared grid grouping (Validator contract
VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022 §3)."""

from __future__ import annotations

import pytest

from carbon.scoring import sealed_grid_common as grid


class Refused(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _refuse(code):
    raise Refused(code)


def _rows(designs=5, conditions=6, cohort=grid.GRID_COHORT):
    return [
        {
            "cohort": cohort,
            "design_id": f"design-{d}",
            "condition_id": f"condition-{c}",
        }
        for d in range(designs)
        for c in range(conditions)
    ]


def _layout(rows, shape=(5, 6)):
    return grid.grid_layout(
        rows,
        design_of=lambda r: r.get("design_id"),
        condition_of=lambda r: r.get("condition_id"),
        shape=shape,
        refuse=_refuse,
    )


def test_a_complete_grid_is_grouped_with_its_own_ids_and_row_indices():
    rows = _rows() + [{"cohort": "probe"}]
    layout = _layout(rows)
    assert layout.designs == tuple(f"design-{d}" for d in range(5))
    assert layout.conditions == tuple(f"condition-{c}" for c in range(6))
    assert len(layout.cells) == 30 and layout.indices == tuple(range(30))
    assert layout.cells[("design-2", "condition-3")] == 2 * 6 + 3
    assert layout.rows_of_design("design-1") == [6 + c for c in range(6)]
    assert layout.rows_of_condition("condition-4") == [d * 6 + 4 for d in range(5)]


def test_rows_outside_the_grid_cohort_are_not_cells():
    rows = [{"cohort": "probe", "design_id": "x", "condition_id": "y"}] + _rows()
    layout = _layout(rows)
    assert layout.indices == tuple(range(1, 31))


def test_a_battery_style_grid_names_cells_by_the_records_own_ids():
    rows = [
        {
            "cohort": grid.GRID_COHORT,
            "record": {"scenario_id": f"scenario-{s}", "candidate_id": f"c{k}"},
        }
        for s in range(4)
        for k in range(35)
    ]
    layout = grid.grid_layout(
        rows,
        design_of=lambda r: r["record"]["candidate_id"],
        condition_of=lambda r: r["record"]["scenario_id"],
        shape=(35, 4),
        refuse=_refuse,
    )
    assert len(layout.designs) == 35 and len(layout.conditions) == 4


@pytest.mark.parametrize(
    ("rows", "shape", "code"),
    [
        (_rows()[:-1], (5, 6), "grid_incomplete"),
        (_rows(4, 6), (5, 6), "grid_shape"),
        (_rows(), (6, 5), "grid_shape"),
        (_rows() + _rows()[:1], (5, 6), "grid_incomplete"),
        (_rows(4, 6) + _rows(1, 5)[:5], (5, 6), "grid_incomplete"),
        ([{**_rows()[0], "condition_id": ""}] + _rows()[1:], (5, 6), "grid_incomplete"),
        ([{**_rows()[0], "design_id": None}] + _rows()[1:], (5, 6), "grid_incomplete"),
    ],
)
def test_a_bank_that_is_not_the_registered_grid_refuses_with_a_closed_code(
    rows, shape, code
):
    with pytest.raises(Refused) as refused:
        _layout(rows, shape)
    assert refused.value.code == code


def test_the_decision_objective_is_the_grids_own_ids_and_the_registered_contract():
    layout = _layout(_rows())
    contract = {"constraints": {"a": 1}}
    objective = grid.decision_objective(layout, contract)
    assert objective == {
        "design_ids": list(layout.designs),
        "condition_ids": list(layout.conditions),
        "decision_contract": contract,
    }
    assert objective["decision_contract"] is contract

"""A headroom cell is graded over the class's targets that CARRY its output (mc-exam-C, Thu 12 Nov; the 5th Motor 1.8
seam, TL-2C's conformance STOP on the push commit 0e4b8436).

Motor 1.8's H-3a / H-3b classes hold targets carrying (pk-pk, OC) and one torque-only sibling target each (the rows with
no recorded lambda: Carbon Validator-Motor R1 cond 5, "NOT OC targets ... they stay in the torque cells").
`attach_cells` required EVERY target of a class to carry EVERY scored output, so the OC cell refused every grade.

Claims:
- A class may hold a target lacking one of its scored outputs. That cell is graded over the carriers only, and the
  sibling still counts in the cells of the outputs it carries.
- The admission n is checked per (class, output) over the carriers.
- A set whose class has NO carrier of a scored output still refuses (the same codes as before).

Every class, value and target here is a SYNTHETIC fixture (`test_pool_physics_score`'s stand targets).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "scripts" / "dev"))

from test_pool_headroom import PASS, admission_doc, cell, headroom_rule
from test_pool_multiclass_regions import plan_document
from test_pool_physics_score import EDGE, IN, STEP, model, stand

from carbon.scoring import pool_grader
from carbon.scoring import pool_physics_score as pps
from carbon.scoring.pool_grader import coverage_plan


def sibling(target_id, errors, u=0.5):
    """A target of the same class carrying ONLY output f (as a torque-only sibling carries only the torque outputs)."""
    n = len(errors)
    return SimpleNamespace(
        target_id=target_id,
        extended=True,
        agen=tuple(range(n)),
        outputs=("f",),
        conditions={"case": target_id},
        designs=tuple((float(i),) for i in range(n)),
        truths=tuple({"f": 0.0} for _ in range(n)),
        u_at=lambda index, name, u=u: u,
        errors=tuple(errors),
    )


def _doc(edge_f_n, edge_g_n):
    return admission_doc(
        [
            cell("fixture-F1", EDGE, "f", 8.0, n=edge_f_n),
            cell("fixture-F1", EDGE, "g", 8.0, n=edge_g_n),  # scored: only e0 carries g
            cell("fixture-F3", STEP, "f", 5.0, n=1),
        ]
    )


def _specs(with_carrier=True):
    specs = [stand("i0", False, [0.1, 0.2, 0.3])]
    if with_carrier:
        specs.append(stand("e0", True, [0.5, 1.5]))
    specs += [sibling("e1", [1.0, 2.0, 3.0]), stand("s0", True, [1.0])]
    plan = coverage_plan(
        plan_document(
            [IN, EDGE, STEP],
            {
                s.target_id: c
                for s, c in zip(
                    specs,
                    [IN, *([EDGE] if with_carrier else []), EDGE, STEP],
                    strict=True,
                )
            },
        )
    )
    return specs, plan


@pytest.fixture
def companion_g(monkeypatch):
    """The model's derive gives every target f and g (as Motor 1.8's gives every target both torque scalars)."""
    monkeypatch.setattr(pool_grader, "_COMPANIONS", {"g"})


def test_without_the_companion_the_siblings_answer_is_invalid():
    """The 6th seam: an answer carrying a scalar its target does not grade was an INVALID answer."""
    assert pool_grader.graded_answer({"f": 1.0, "g": 2.0}, ("f",)) is None


def test_a_companion_is_dropped_never_graded(companion_g):
    assert pool_grader.graded_answer({"f": 1.0, "g": 2.0}, ("f",)) == {"f": 1.0}
    assert (
        pool_grader.graded_answer({"f": 1.0, "h": 2.0}, ("f",)) is None
    )  # an unregistered extra still refuses
    assert pool_grader.graded_answer({"f": 1.0, "g": 2.0}, ("f", "g")) == {
        "f": 1.0,
        "g": 2.0,
    }


def test_a_cell_is_graded_over_its_carriers_and_the_sibling_counts_where_it_carries(
    companion_g,
):
    specs, plan = _specs()
    doc = _doc(edge_f_n=5, edge_g_n=2)  # f: e0 2 + e1 3 cases; g: e0 only
    rule = pps.attach_cells(headroom_rule(doc), doc, plan, (tuple(specs),))
    record = pps.accuracy_record(specs, model(specs), plan, rule, None)
    rows = {(r["class"], r["output"]): r for r in record["rows"]}
    assert rows[(EDGE, "f")]["n"] == 5 and rows[(EDGE, "g")]["n"] == 2
    by_target = {
        s.target_id: pps.target_cells(s, model(specs), {}, plan, rule) for s in specs
    }
    assert set(by_target["e1"]) == {("fixture-F1", EDGE, "f")}  # never the g cell
    assert by_target["e1"][("fixture-F1", EDGE, "f")][1] == 3
    assert by_target["e0"][("fixture-F1", EDGE, "g")][1] == 2
    assert pps.family_value(specs, model(specs), {}, plan, rule) is not None


def test_the_admission_n_is_checked_per_output_over_the_carriers(companion_g):
    specs, plan = _specs()
    # the class's whole case count (5) on the g cell is NOT the carriers' count (2): a different exam
    doc = _doc(edge_f_n=5, edge_g_n=5)
    with pytest.raises(
        pps.PhysicsRefused, match="headroom_admission_n_is_not_the_exams_case_count"
    ):
        pps.attach_cells(headroom_rule(doc), doc, plan, (tuple(specs),))


def test_a_class_with_no_carrier_of_a_scored_output_still_refuses(companion_g):
    specs, plan = _specs(
        with_carrier=False
    )  # EDGE holds only the f-only sibling: g has no carrier
    doc = _doc(edge_f_n=3, edge_g_n=2)
    with pytest.raises(
        pps.PhysicsRefused, match="scoring_cells_output_not_an_output_of_its_class"
    ):
        pps.attach_cells(headroom_rule(doc), doc, plan, (tuple(specs),))


def test_every_target_carrying_every_output_is_unchanged():
    """The pre-fix shape (no sibling): the same cells, n and record as before."""
    specs = [
        stand("i0", False, [0.1, 0.2]),
        stand("e0", True, [0.5, 1.5]),
        stand("s0", True, [1.0]),
    ]
    plan = coverage_plan(
        plan_document([IN, EDGE, STEP], {"i0": IN, "e0": EDGE, "s0": STEP})
    )
    doc = admission_doc(
        [
            cell("fixture-F1", EDGE, "f", 8.0, n=2),
            cell("fixture-F1", EDGE, "g", 8.0, n=2, tests={**PASS, "C": "FAIL"}),
            cell("fixture-F3", STEP, "f", 5.0, n=1),
        ]
    )
    rule = pps.attach_cells(headroom_rule(doc), doc, plan, (tuple(specs),))
    assert rule.cells.scored == (("fixture-F1", EDGE, "f"), ("fixture-F3", STEP, "f"))
    assert {
        k: v[1]
        for k, v in pps.target_cells(specs[1], model(specs), {}, plan, rule).items()
    } == {("fixture-F1", EDGE, "f"): 2}

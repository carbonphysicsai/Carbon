"""P1: a REGISTERED pool-only version (model-eval ruling 22 Nov 2026 04:41:52Z).

Claims:
- a pool-only version runs NO base measure (no sealed grid): its gates are the pool's (physics, speed, in-range accuracy);
- A per set is the physics family value, and the owner's C rule is kept with C = that set's own physics A: each set's
  D = min(menu D, A_set), so a model never takes more decision credit than its accuracy earns;
- the SE basis recomposes the graded total with that cap;
- a pool-only bank holding a sealed row, or a pool-only registration without a physics rule and a menu, refuses;
- every version without the flag is unchanged (the accuracy-only suite runs the same fixture with the base measure).

Every target, case, key and value here is a SYNTHETIC fixture (the toy targets of test_pool_plugin).
"""

from __future__ import annotations

import dataclasses
import json
import statistics
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_pool_accuracy_only import _accuracy_sets, _menu_d
from test_pool_exam import ARGUMENTS, CEILING, FAST, exam_rows, toy_binding
from test_pool_menu import KEY, _rowcheck, _tasks
from test_pool_menu import _rule as menu_rule
from test_pool_multiclass_regions import (  # noqa: F401  (geometric_v1_stand_in is a fixture)
    geometric_v1_stand_in,
)
from test_pool_physics_score import _registered
from test_pool_plugin import good_serve

from carbon.scoring import pool_exam, pool_menu, pool_version
from carbon.scoring import pool_physics_score as pps


def _no_base_measure(**_kwargs):
    raise AssertionError("a pool-only version must never run a base measure")


def _grade(the_sets, *, threshold=2.5, keep_sealed=False):
    policies, material = _registered(the_sets, threshold)
    policies = dataclasses.replace(
        policies,
        physics=dataclasses.replace(policies.physics, target_kind="accuracy_only"),
        menu=menu_rule(),
        pool_only=True,
    )
    tasks = _tasks()
    rows = [
        r
        for r in exam_rows(the_sets)
        if keep_sealed or r["cohort"] == pool_exam.POOL_COHORT
    ]
    for row in pool_menu.bank_rows(tasks, ("x", "y")):
        rows.append(
            {
                "case_id": "menu-row",
                "inputs": row,
                "reference": None,
                "cohort": pool_exam.POOL_COHORT,
            }
        )
    outputs = good_serve([r["inputs"] for r in rows])
    capture = {}
    result = pool_exam.measure_pool(
        binding=toy_binding(),
        sets=the_sets,
        policies=policies,
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        base_measure=_no_base_measure,
        base_arguments=ARGUMENTS,
        speed_call_seconds=FAST,
        ceiling_seconds=CEILING,
        capture=capture,
        menu_tasks=tasks,
        menu_key=KEY,
        menu_rowcheck=_rowcheck(rows, outputs),
        menu_rowcheck_key=KEY,
        **material,
    )
    return result, capture


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_pool_only_version_runs_no_base_measure_and_caps_d_by_its_own_physics_a(
    monkeypatch,
):
    the_sets = _accuracy_sets()
    seen = []
    real = pps.family_value

    def recording(*a):
        value = real(*a)
        seen.append((frozenset(s.target_id for s in a[0]), value))
        return value

    monkeypatch.setattr(pps, "family_value", recording)
    result, _capture = _grade(the_sets)
    assert set(result["gates"]) == {
        pool_exam.PHYSICS_GATE,
        pool_exam.SPEED_GATE,
        pool_exam.ACCURACY_GATE,
    }
    assert all(result["gates"].values())
    per_set = dict(seen)
    a_sets = [per_set[frozenset(t.target_id for t in group)] for group in the_sets]
    assert result["A"] == pytest.approx(statistics.fmean(a_sets), abs=1e-15)
    menu_d = _menu_d()
    assert result["D"] == pytest.approx(
        statistics.fmean(min(menu_d, a) for a in a_sets), abs=1e-15
    )
    assert "design_fidelity" not in result
    shown = json.dumps(pool_exam.public(result))
    assert "menu" not in shown and "accuracy" not in shown


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_bootstrap_recomposes_the_graded_total_with_the_a_cap():
    result, capture = _grade(_accuracy_sets(per_class=2))
    basis = capture["se_basis"]
    assert basis["c_is_a"] is True and basis["c"] is None
    graded = 0.5 * result["A"] + 0.5 * result["D"]
    assert basis["total"] == pytest.approx(graded, abs=1e-15)
    assert pool_exam.total_of_targets(basis, basis["sets"]) == pytest.approx(
        graded, abs=1e-15
    )


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_failed_gate_scores_nothing_without_a_base_a():
    result, capture = _grade(_accuracy_sets(), threshold=1.5)
    assert result["gates"][pool_exam.ACCURACY_GATE] is False and result["D"] == 0.0
    assert capture["se_basis"] == {"gated": True}


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_pool_only_bank_with_a_sealed_row_refuses():
    with pytest.raises(pool_exam.ExamRefused) as caught:
        _grade(_accuracy_sets(), keep_sealed=True)
    assert caught.value.code == "pool_only_bank_holds_sealed_rows"


def test_the_flag_registers_as_true_only_and_needs_a_physics_rule_and_a_menu(tmp_path):
    document = json.loads(pool_version.CONSTANTS.read_bytes())
    base = json.loads(json.dumps(document["versions"]["chip-cold-plate 1.6"]))
    path = tmp_path / "pool_constants.json"

    def read(**extra):
        entry = {**base, **extra}
        path.write_text(json.dumps({**document, "versions": {"fixture 9.9": entry}}))
        return pool_version.registered_policies("fixture", "9.9", path=path)

    assert read().pool_only is False  # absent: every registered version
    for bad in ("true", 1, False, None, "HUMAN_INPUT"):
        with pytest.raises(pool_version.PoolConstantsNotRegistered):
            read(pool_only=bad)
    # a version with neither a physics rule nor a menu cannot be pool-only
    assert "physics" not in base and "menu" not in base
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        read(pool_only=True)


def test_split_rows_keeps_the_both_cohorts_rule_for_every_other_version():
    sealed = {"cohort": "sealed"}
    pooled = {"cohort": pool_exam.POOL_COHORT}
    assert pool_exam.split_rows([sealed, pooled]) == ([0], [1])
    for rows in ([pooled], [sealed], []):
        with pytest.raises(pool_exam.ExamRefused) as caught:
            pool_exam.split_rows(rows)
        assert caught.value.code == "exam_bank_needs_sealed_rows_and_pool_rows"
    assert pool_exam.split_rows([pooled, pooled], pool_only=True) == ([], [0, 1])
    with pytest.raises(pool_exam.ExamRefused) as caught:
        pool_exam.split_rows([sealed, pooled], pool_only=True)
    assert caught.value.code == "pool_only_bank_holds_sealed_rows"
    with pytest.raises(pool_exam.ExamRefused) as caught:
        pool_exam.split_rows([], pool_only=True)
    assert caught.value.code == "exam_bank_needs_pool_rows"

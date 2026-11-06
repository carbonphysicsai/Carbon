"""Headroom scoring on the pool path (owner 6 Nov via EQ; HEADROOM_SCORING_PLAN rev 2 f3f47127, provisional).

Claims, for a version registering ``scoring: "headroom"``:
1. A class is scored only when its sealed admission file reads PASS on all five tests (H / C / O / R / V); the numbers
   the grader can check (A_c >= H_min, its lower bound >= H_lo, n >= n_min, n == the exam's case count) are re-checked,
   and a PASS they contradict refuses (fail closed).
2. S_c = clip(ln(A_c / E_c) / ln(A_c), 0, 1) (or the linear form), E_c the geometric mean of max(|err| / U, 1):
   0 = the best classical method, 1 = reference accuracy.
3. The 5 Nov aggregation, total rule, in-range gate, laws record and SE are reused: the target bootstrap recomposes the
   graded total exactly.
4. The owner's values (skill form, H_min, H_lo, n_min) are registered with no default.

Every class, anchor and threshold here is a SYNTHETIC fixture.
"""

from __future__ import annotations

import dataclasses
import json
import math
import statistics
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "scripts" / "dev"))

from test_pool_multiclass_regions import (  # noqa: F401  (geometric_v1_stand_in is a fixture)
    geometric_v1_stand_in,
    plan_document,
)
from test_pool_physics_score import (
    EDGE,
    STEP,
    _measure,
    _registered,
    _sets,
    model,
    stand,
    stand_set,
)

from carbon.scoring import pool_exam
from carbon.scoring import pool_physics_score as pps
from carbon.scoring.pool_grader import coverage_plan

PASS = dict.fromkeys(pps.ADMISSION_TESTS, "PASS")


def cell(family, name, output, anchor, *, lo=None, n=2, tests=None):
    return {
        "family": family,
        "class": name,
        "output": output,
        "anchor_u": anchor,
        "anchor_lo_u": anchor if lo is None else lo,
        "n": n,
        "tests": dict(PASS if tests is None else tests),
    }


def admission_doc(cells):
    return {
        "schema": pps.HEADROOM_SCHEMA,
        "families": {"fixture-F1": [EDGE], "fixture-F3": [STEP]},
        "cells": cells,
    }


DOC = admission_doc(
    [
        cell("fixture-F1", EDGE, "f", 8.0),
        cell("fixture-F1", EDGE, "g", 8.0, tests={**PASS, "C": "FAIL"}),  # report-only
        cell("fixture-F3", STEP, "f", 5.0, n=1),
    ]
)


def headroom_rule(doc=DOC, *, form="log", h_min=4.0, h_lo=2.5, n_min=1, gate=1.0):
    return pps.PhysicsRule(
        cells_sha256=pps.headroom_admission(
            doc, _thresholds(h_min, h_lo, n_min)
        ).sha256,
        gate_statistic="p90",
        gate_threshold=gate,
        gate_cases="agen",
        enters="a",
        ad_split=0.5,
        total_rule="half_a_half_d",
        cell_scale=None,
        scoring="headroom",
        skill_form=form,
        h_min=h_min,
        h_lo=h_lo,
        n_min=n_min,
    )


def _thresholds(h_min, h_lo, n_min):
    return pps.PhysicsRule(
        cells_sha256="0" * 64,
        gate_statistic="p90",
        gate_threshold=1.0,
        gate_cases="agen",
        enters="a",
        ad_split=0.5,
        total_rule="half_a_half_d",
        cell_scale=None,
        scoring="headroom",
        skill_form="log",
        h_min=h_min,
        h_lo=h_lo,
        n_min=n_min,
    )


def attached(specs, plan, doc=DOC, **kw):
    return pps.attach_cells(headroom_rule(doc, **kw), doc, plan, (tuple(specs),))


# ---------------------------------------------------------------- 2. the skill


@pytest.mark.parametrize(
    "form, anchor, error, expected",
    [
        ("log", 8.0, 8.0, 0.0),  # the best classical method scores 0
        ("log", 8.0, 1.0, 1.0),  # reference accuracy scores 1
        ("log", 8.0, 2.0, 2 / 3),  # each halving of 8 is a third
        ("log", 8.0, 16.0, 0.0),  # worse than the fits: 0, never negative
        ("linear", 8.0, 4.5, 0.5),
    ],
)
def test_the_skill_is_zero_at_the_anchor_and_one_at_reference_accuracy(
    form, anchor, error, expected
):
    rule = dataclasses.replace(headroom_rule(), skill_form=form)
    assert pps.skill(rule, anchor, error) == pytest.approx(expected, abs=1e-12)


# ---------------------------------------------------------------- 1. the admission file


def test_only_all_pass_cells_are_admitted_and_the_numbers_are_rechecked():
    admission = pps.headroom_admission(DOC, _thresholds(4.0, 2.5, 1))
    assert admission.scored == (("fixture-F1", EDGE, "f"), ("fixture-F3", STEP, "f"))
    assert admission.not_admitted == (("fixture-F1", EDGE, "g"),)
    assert admission.anchor(("fixture-F3", STEP, "f")) == 5.0
    # a PASS the numbers contradict is a structural fault, never silently dropped
    for bad in (
        cell("fixture-F1", EDGE, "f", 3.0),  # A below H_min
        cell("fixture-F1", EDGE, "f", 8.0, lo=2.0),  # lower bound below H_lo
        cell("fixture-F1", EDGE, "f", 8.0, n=1),  # n below n_min
    ):
        with pytest.raises(pps.PhysicsRefused, match="contradicts_the_thresholds"):
            pps.headroom_admission(admission_doc([bad]), _thresholds(4.0, 2.5, 2))
    # a FAIL with the same numbers is just report-only
    fail = cell("fixture-F1", EDGE, "f", 3.0, tests={**PASS, "H": "FAIL"})
    with pytest.raises(pps.PhysicsRefused, match="admits_no_cell"):
        pps.headroom_admission(admission_doc([fail]), _thresholds(4.0, 2.5, 1))


@pytest.mark.parametrize(
    "mutate, code",
    [
        (lambda d: d.update(schema="x"), "admission_malformed"),
        (lambda d: d["cells"][0]["tests"].pop("V"), "cell_malformed"),
        (lambda d: d["cells"][0]["tests"].update(H="MAYBE"), "cell_malformed"),
        (lambda d: d["cells"][0].update(anchor_lo_u=99.0), "cell_malformed"),
        (lambda d: d["cells"].append(dict(d["cells"][0])), "duplicate_cell"),
        (lambda d: d["families"].update({"x": [EDGE]}), "class_in_two_families"),
    ],
)
def test_a_malformed_admission_refuses(mutate, code):
    document = json.loads(json.dumps(DOC))
    mutate(document)
    with pytest.raises(pps.PhysicsRefused, match=code):
        pps.headroom_admission(document, _thresholds(4.0, 2.5, 1))


@pytest.mark.parametrize(
    "change, code",
    [
        ({"skill_form": None}, "skill_form_is_human_input"),
        ({"skill_form": "sqrt"}, "skill_form_must_be"),
        ({"h_min": None}, "h_min_is_human_input"),
        ({"h_lo": 1.0}, "h_lo_must_exceed_1"),
        ({"h_lo": 5.0}, "h_lo_must_not_exceed_h_min"),
        ({"n_min": 0}, "n_min_must_be"),
        ({"cell_scale": "agen_scales"}, "headroom_has_no_cell_scale"),
    ],
)
def test_the_owners_values_have_no_default(change, code):
    with pytest.raises(pps.PhysicsRefused, match=code):
        pps.check_rule(dataclasses.replace(headroom_rule(), **change))


def test_headroom_values_refuse_on_a_cells_version():
    from test_pool_physics_score import rule as cells_rule

    with pytest.raises(pps.PhysicsRefused, match="need_headroom_scoring"):
        pps.check_rule(dataclasses.replace(cells_rule(), h_min=4.0))


# ---------------------------------------------------------------- the family value, by hand


def test_the_family_value_is_the_mean_of_admitted_skills_on_floored_geometric_errors():
    specs, plan = (
        stand_set()
    )  # U = 0.5; e0 errors 0.5, 1.5 (e = 1, 3); s0 error 1.0 (e = 2)
    rule = attached(specs, plan)
    got = pps.family_value(specs, model(specs), {}, plan, rule)
    f1 = math.log(8.0 / math.sqrt(3.0)) / math.log(
        8.0
    )  # (EDGE, f) only: (EDGE, g) is not admitted
    f3 = math.log(5.0 / 2.0) / math.log(5.0)
    assert got == pytest.approx(statistics.fmean([f1, f3]), abs=1e-12)
    # an error below 1 U earns nothing more than 1 U (the floor)
    better = [stand(s.target_id, s.extended, [e / 10 for e in s.errors]) for s in specs]
    assert pps.family_value(better, model(better), {}, plan, rule) == pytest.approx(1.0)


def test_the_structure_refuses_a_different_exam_or_a_zero_u():
    specs, plan = stand_set()
    wrong_n = admission_doc([cell("fixture-F1", EDGE, "f", 8.0, n=5)])
    with pytest.raises(pps.PhysicsRefused, match="n_is_not_the_exams_case_count"):
        attached(specs, plan, wrong_n)
    zero_u = [
        stand("e0", True, [0.5, 1.5], u=0.0) if s.target_id == "e0" else s
        for s in specs
    ]
    with pytest.raises(pps.PhysicsRefused, match="headroom_output_with_zero_u"):
        attached(zero_u, plan)


def test_the_record_carries_each_cells_class_error_and_skill_in_custody():
    specs, plan = stand_set()
    record = pps.accuracy_record(specs, model(specs), plan, attached(specs, plan))
    rows = {(r["class"], r["output"]): r for r in record["rows"]}
    assert rows[(EDGE, "f")]["admitted"] is True
    assert rows[(EDGE, "f")]["class_error_u"] == pytest.approx(math.sqrt(3.0))
    assert rows[(EDGE, "f")]["skill"] == pytest.approx(
        math.log(8.0 / math.sqrt(3.0)) / math.log(8.0)
    )
    assert rows[(EDGE, "g")]["admitted"] is False and rows[(EDGE, "g")]["skill"] is None


# ---------------------------------------------------------------- 3. the official grade + SE


def _headroom_registered(the_sets, policies, material):
    counts = {}
    plan = coverage_plan(material["coverage_plan"])
    for group in the_sets:
        for spec in group:
            name = plan.class_of(spec.target_id)
            counts[name] = counts.get(name, 0) + len(spec.agen)
    doc = admission_doc(
        [
            cell("fixture-F1", EDGE, "f", 8.0, n=counts[EDGE]),
            cell("fixture-F1", EDGE, "g", 6.0, n=counts[EDGE]),
            cell("fixture-F3", STEP, "f", 5.0, n=counts[STEP]),
        ]
    )
    rule = headroom_rule(doc, n_min=12, gate=2.5)  # the fixture's own gate threshold
    return dataclasses.replace(policies, physics=rule), {
        **material,
        "scoring_cells": doc,
    }


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_official_grade_scores_headroom_and_the_se_recomposes_it_exactly():
    the_sets = _sets(per_class=2)
    policies, material = _registered(the_sets, threshold=2.5)
    policies, material = _headroom_registered(the_sets, policies, material)
    result, capture = _measure(the_sets, policies, material)
    # the model answers the bank's rounded rows, so its error is near (not exactly) 2 U: a skill strictly inside (0, 1)
    # (the exact arithmetic is pinned on the stand-in set above)
    assert result["gates"][pool_exam.ACCURACY_GATE] is True and result["D"] > 0
    assert 0.0 < result["A"] < 1.0
    basis = capture["se_basis"]
    assert pool_exam.total_of_targets(basis, basis["sets"]) == pytest.approx(
        0.5 * result["A"] + 0.5 * result["D"], abs=1e-12
    )
    spread, sizes = pool_exam.target_bootstrap_se(basis, "sha256:" + "ab" * 32)
    assert math.isfinite(spread) and sizes == [6, 6]
    rows = result["pool"]["accuracy"]["rows"]
    assert any(r.get("admitted") for r in rows)
    assert "anchor" not in json.dumps(pool_exam.public(result))


# ---------------------------------------------------------------- 4. registration


def test_headroom_registers_with_no_default(tmp_path):
    from carbon.scoring import pool_version

    document = json.loads(pool_version.CONSTANTS.read_bytes())
    base = json.loads(json.dumps(document["versions"]["chip-cold-plate 1.6"]))
    path = tmp_path / "pool_constants.json"
    good = {
        "cells_sha256": "c" * 64,
        "gate_statistic": "p90",
        "gate_threshold": 1.0,
        "gate_cases": "pool",
        "enters": "a",
        "ad_split": 0.5,
        "total_rule": "half_a_half_d",
        "scoring": "headroom",
        "skill_form": "log",
        "h_min": 4,
        "h_lo": 2.5,
        "n_min": 12,
    }

    def read(physics):
        path.write_text(
            json.dumps(
                {**document, "versions": {"fixture 9.9": {**base, "physics": physics}}}
            )
        )
        return pool_version.registered_policies("fixture", "9.9", path=path).physics

    rule = read(good)
    assert rule.scoring == "headroom" and rule.cell_scale is None and rule.n_min == 12
    for key in ("skill_form", "h_min", "h_lo", "n_min"):
        for bad in (pool_version.HUMAN_INPUT, None):
            with pytest.raises(pool_version.PoolConstantsNotRegistered):
                read({**good, key: bad})
        with pytest.raises(pool_version.PoolConstantsNotRegistered):
            read({k: v for k, v in good.items() if k != key})
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        read({**good, "cell_scale": "agen_scales"})  # headroom registers no cell scale


# ---------------------------------------------------------------- the TL's writer


def test_the_writer_validates_writes_once_and_prints_counts_only(tmp_path, capsys):
    import headroom_admission as writer

    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps({k: v for k, v in DOC.items() if k != "schema"}))
    out = tmp_path / "admission.json"
    args = ["--h-min", "4", "--h-lo", "2.5", "--n-min", "1"]
    assert writer.main(["write", "--draft", str(draft), "--out", str(out), *args]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["admitted"] == 2 and printed["not_admitted"] == 1
    assert printed["sha256"] == headroom_rule().cells_sha256
    assert writer.main(["check", str(out), *args]) == 0
    capsys.readouterr()
    assert writer.main(["write", "--draft", str(draft), "--out", str(out), *args]) == 1
    assert "out_exists" in capsys.readouterr().out
    assert (
        writer.main(
            ["check", str(out), "--h-min", "9", "--h-lo", "2.5", "--n-min", "1"]
        )
        == 1
    )
    assert EDGE not in capsys.readouterr().out  # no class name is ever printed

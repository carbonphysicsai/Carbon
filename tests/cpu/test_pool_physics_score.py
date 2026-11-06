"""Physics scoring on the pool path: the in-range accuracy gate, the accuracy record and the family layer.

Claims (the owner's 5 Nov decisions; EQ 17:45 record rule), for a NEW version with a physics rule only:
1. In-range accuracy is a GATE (pass/fail, never points); its statistic and threshold are HUMAN_INPUT: a rule without
   them refuses to grade, never defaulted.
2. Every grade RECORDS median / p90 / max |err|/U and n per class x output, in range and out of range, scored or not,
   into the custody record; `public` never carries it.
3. Only the registered (family, class, output) cells score; families with a scored cell weigh equally.
4. A version without a physics rule is unchanged: no new gate, no record, the same A, D and gates.

Every class name, family name, threshold and value here is a SYNTHETIC fixture, never a production value.
"""

from __future__ import annotations

import dataclasses
import json
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_pool_exam import (
    ARGUMENTS,
    CEILING,
    FAST,
    POLICIES,
    exam_rows,
    grade,
    toy_binding,
)
from test_pool_multiclass_regions import (  # noqa: F401  (geometric_v1_stand_in is a fixture)
    geometric_v1_stand_in,
    plan_document,
    sha,
    sums_text,
)
from test_pool_plugin import SHELL, fake_measure, good_serve
from test_pool_plugin import toy_target as exam_target

from carbon.scoring import pool_exam
from carbon.scoring import pool_physics_score as pps
from carbon.scoring.design_fidelity import benefit
from carbon.scoring.pool_grader import coverage_plan

IN, EDGE, STEP = "fixture:in", "fixture:edge", "fixture:step"
CELLS = {
    "schema": pps.SCORING_CELLS_SCHEMA,
    "families": {"fixture-F1": [EDGE], "fixture-F3": [STEP]},
    "scored": [
        ["fixture-F1", EDGE, "f"],
        ["fixture-F1", EDGE, "g"],
        ["fixture-F3", STEP, "f"],
    ],
}


def rule(statistic="p90", threshold=1.0, cells=CELLS, enters="a_gen"):
    return pps.PhysicsRule(
        cells_sha256=pps.cell_map(cells).sha256,
        gate_statistic=statistic,
        gate_threshold=threshold,
        enters=enters,
    )


# ---------------------------------------------------------------- stand-in targets (record / family arithmetic)


def stand(target_id, extended, errors, u=0.5):
    """A target whose reserved points have truth 0 on f and g; ``errors`` = the model's error per point (f and g alike)."""
    n = len(errors)
    return SimpleNamespace(
        target_id=target_id,
        extended=extended,
        agen=tuple(range(n)),
        outputs=("f", "g"),
        conditions={"case": target_id},
        designs=tuple((float(i),) for i in range(n)),
        truths=tuple({"f": 0.0, "g": 0.0} for _ in range(n)),
        u_at=lambda index, name, u=u: u,
        errors=tuple(errors),
    )


def model(specs, scale=1.0):
    by_case = {s.target_id: s.errors for s in specs}

    def predict(conditions, designs):
        errs = by_case[conditions["case"]]
        return [
            {"f": scale * errs[int(d[0])], "g": scale * errs[int(d[0])]}
            for d in designs
        ]

    return predict


def stand_set():
    specs = [
        stand("i0", False, [0.1, 0.2, 0.3, 0.4, 0.5]),  # |err|/U = 0.2 .. 1.0
        stand("e0", True, [0.5, 1.5]),
        stand("s0", True, [1.0]),
        stand("x0", True, [2.0]),  # a report-only out-of-range class: in no family
    ]
    plan = coverage_plan(
        plan_document(
            [IN, EDGE, STEP, "fixture:extra"],
            {"i0": IN, "e0": EDGE, "s0": STEP, "x0": "fixture:extra"},
        )
    )
    return specs, plan


def attached(specs, plan, **kw):
    return pps.attach_cells(rule(**kw), kw.get("cells", CELLS), plan, (tuple(specs),))


# ---------------------------------------------------------------- 1. the rule: HUMAN_INPUT refuses


@pytest.mark.parametrize(
    "kw, code",
    [
        ({"statistic": None}, "accuracy_gate_statistic_is_human_input"),
        ({"threshold": None}, "accuracy_gate_threshold_is_human_input"),
        ({"statistic": "mean"}, "statistic_must_be_median_p90_or_max"),
        ({"threshold": -1.0}, "threshold_must_be"),
        ({"threshold": {"f": float("nan")}}, "threshold_must_be"),
        ({"enters": "replace_a"}, "physics_enters_must_be_a_gen"),
    ],
)
def test_an_incomplete_rule_refuses_never_defaults(kw, code):
    with pytest.raises(pps.PhysicsRefused, match=code):
        pps.check_rule(rule(**kw))


@pytest.mark.parametrize(
    "mutate, code",
    [
        (lambda d: d.update(schema="x"), "scoring_cells_malformed"),
        (
            lambda d: d["families"].update({"fixture-F2": [EDGE]}),
            "class_in_two_families",
        ),
        (
            lambda d: d["scored"].append(["fixture-F3", EDGE, "f"]),
            "scored_cell_invalid",
        ),
        (lambda d: d["scored"].append(["fixture-F1", EDGE, "f"]), "duplicate_cell"),
        (lambda d: d.update(scored=[]), "scored_cell_invalid"),
    ],
)
def test_the_cell_map_refuses_a_malformed_document(mutate, code):
    document = json.loads(json.dumps(CELLS))
    mutate(document)
    with pytest.raises(pps.PhysicsRefused, match=code):
        pps.cell_map(document)


def test_the_cell_map_binds_by_its_canonical_digest():
    a = pps.cell_map(CELLS)
    reordered = {
        "scored": list(reversed(CELLS["scored"])),
        **{k: CELLS[k] for k in ("schema", "families")},
    }
    assert pps.cell_map(reordered).scored == a.scored  # the cells are the same set
    assert a.sha256 == sha(pps.cell_map_bytes(CELLS).decode())


# ---------------------------------------------------------------- 2. the record and the gate


def test_the_record_holds_every_class_and_output_and_the_gate_reads_the_in_range_rows():
    specs, plan = stand_set()
    record = pps.accuracy_record(specs, model(specs), plan, attached(specs, plan))
    assert record["schema"] == pps.RECORD_SCHEMA
    rows = {(r["class"], r["output"]): r for r in record["rows"]}
    assert set(rows) == {
        (c, o) for c in (IN, EDGE, STEP, "fixture:extra") for o in ("f", "g")
    }
    inr = rows[(IN, "f")]
    assert inr["range"] == "in" and inr["family"] is None and inr["scored"] is False
    assert inr["n"] == 5
    assert inr["median"] == pytest.approx(0.6)
    assert inr["p90"] == pytest.approx(0.92)  # inclusive linear quantile of 0.2 .. 1.0
    assert inr["max"] == pytest.approx(1.0)
    assert inr["verdict"] == "PASS"  # p90 0.92 <= 1.0
    edge = rows[(EDGE, "g")]
    assert (
        edge["range"] == "out"
        and edge["family"] == "fixture-F1"
        and edge["scored"] is True
    )
    assert (edge["n"], edge["max"], edge["verdict"]) == (2, pytest.approx(3.0), None)
    extra = rows[("fixture:extra", "f")]
    assert (
        extra["family"] is None
        and extra["scored"] is False
        and extra["verdict"] is None
    )
    assert record["gate"] == {"statistic": "p90", "passed": True}


@pytest.mark.parametrize(
    "statistic, threshold, passed",
    [
        ("median", 0.6, True),
        ("median", 0.59, False),
        ("max", 1.0, True),
        ("max", 0.99, False),
        ("p90", {"f": 1.0, "g": 0.9}, False),  # one output fails: the gate fails
    ],
)
def test_the_gate_compares_the_registered_statistic_with_the_threshold(
    statistic, threshold, passed
):
    specs, plan = stand_set()
    r = attached(specs, plan, statistic=statistic, threshold=threshold)
    assert pps.accuracy_record(specs, model(specs), plan, r)["gate"]["passed"] is passed


def test_the_gate_never_scores_out_of_range_error():
    specs, plan = stand_set()
    worse = model(specs)
    record = pps.accuracy_record(specs, worse, plan, attached(specs, plan))
    # the out-of-range rows hold far larger errors (up to 4 U) and the gate still passes on the in-range class alone
    assert max(
        r["max"] for r in record["rows"] if r["range"] == "out"
    ) == pytest.approx(4.0)
    assert record["gate"]["passed"] is True


# ---------------------------------------------------------------- 3. the family layer


def test_only_scored_cells_count_and_surviving_families_weigh_equally():
    specs, plan = stand_set()
    scales = {"f": 0.5, "g": 0.5}
    r = attached(specs, plan)
    got = pps.family_value(specs, model(specs), scales, plan, r)
    edge_f = statistics.fmean([benefit(0.5 / 0.5), benefit(1.5 / 0.5)])
    f1 = statistics.fmean(
        [edge_f, edge_f]
    )  # (EDGE, f) and (EDGE, g) carry the same errors
    f3 = benefit(1.0 / 0.5)
    assert got == pytest.approx(statistics.fmean([f1, f3]), abs=1e-15)
    # the in-range class and the report-only class never enter: a model perfect there scores the same
    perfect_elsewhere = [
        (
            stand(s.target_id, s.extended, [0.0] * len(s.errors))
            if s.target_id in ("i0", "x0")
            else s
        )
        for s in specs
    ]
    assert got == pps.family_value(
        perfect_elsewhere, model(perfect_elsewhere), scales, plan, r
    )


def test_a_family_is_one_vote_however_many_cells_it_scores():
    specs, plan = stand_set()
    one_cell = json.loads(json.dumps(CELLS))
    one_cell["scored"] = [["fixture-F1", EDGE, "f"], ["fixture-F3", STEP, "f"]]
    scales = {"f": 0.5, "g": 0.5}
    a = pps.family_value(specs, model(specs), scales, plan, attached(specs, plan))
    b = pps.family_value(
        specs, model(specs), scales, plan, attached(specs, plan, cells=one_cell)
    )
    assert a == pytest.approx(b, abs=1e-15)


# ---------------------------------------------------------------- the exam's structure (refused once, before grading)


def test_structural_faults_refuse_at_attach():
    specs, plan = stand_set()
    with pytest.raises(pps.PhysicsRefused, match="sha256_mismatch"):
        pps.attach_cells(
            rule(), {**CELLS, "scored": CELLS["scored"][:1]}, plan, (tuple(specs),)
        )
    in_family = {**CELLS, "families": {**CELLS["families"], "fixture-F0": [IN]}}
    with pytest.raises(pps.PhysicsRefused, match="family_class_must_be_out_of_range"):
        attached(specs, plan, cells=in_family)
    no_cases = [stand("s0", True, []) if s.target_id == "s0" else s for s in specs]
    with pytest.raises(pps.PhysicsRefused, match="scoring_cell_without_cases_in_a_set"):
        attached(no_cases, plan)
    no_gate = [stand("i0", False, []) if s.target_id == "i0" else s for s in specs]
    with pytest.raises(pps.PhysicsRefused, match="in_range_class_without_gate_cases"):
        attached(no_gate, plan)
    exact = [
        stand("i0", False, [0.1], u=0.0) if s.target_id == "i0" else s for s in specs
    ]
    with pytest.raises(pps.PhysicsRefused, match="output_with_zero_u"):
        attached(exact, plan)
    with pytest.raises(pps.PhysicsRefused, match="threshold_missing_for_an_output"):
        attached(specs, plan, threshold={"f": 1.0})
    mixed = specs + [stand("i1", True, [0.1])]
    mixed_plan = coverage_plan(
        plan_document(
            [IN, EDGE, STEP, "fixture:extra"],
            {"i0": IN, "i1": IN, "e0": EDGE, "s0": STEP, "x0": "fixture:extra"},
        )
    )
    with pytest.raises(pps.PhysicsRefused, match="mixes_in_range_and_out_of_range"):
        attached(mixed, mixed_plan)


# ---------------------------------------------------------------- 4. the official grade (measure_pool)


def _sets():
    return tuple(
        (
            exam_target(f"in{s}", 30 + s),
            exam_target(f"edge{s}", 40 + s, shell=SHELL),
            exam_target(f"step{s}", 50 + s, shell=SHELL),
        )
        for s in range(2)
    )


def _registered(the_sets, threshold):
    targets = {
        t.target_id: {"in": IN, "edge": EDGE, "step": STEP}[
            t.target_id.rstrip("0123456789")
        ]
        for group in the_sets
        for t in group
    }
    document = plan_document([IN, EDGE, STEP], targets)
    plan = coverage_plan(document)
    sums = sums_text(plan.sha256)
    policies = dataclasses.replace(
        POLICIES,
        optimizer=dataclasses.replace(
            POLICIES.optimizer,
            coverage_plan_sha256=plan.sha256,
            coverage_plan_sums_sha256=sha(sums),
        ),
        physics=rule(threshold=threshold),
    )
    return policies, {
        "coverage_plan": document,
        "coverage_plan_sums": sums,
        "scoring_cells": CELLS,
    }


def _measure(the_sets, policies, material, serve=good_serve):
    rows = exam_rows(the_sets)
    outputs = serve([r["inputs"] for r in rows])
    capture = {}
    result = pool_exam.measure_pool(
        binding=toy_binding(),
        sets=the_sets,
        policies=policies,
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        base_measure=fake_measure,
        base_arguments=ARGUMENTS,
        speed_call_seconds=FAST,
        ceiling_seconds=CEILING,
        capture=capture,
        **material,
    )
    return result, capture


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_passing_model_is_scored_and_the_record_stays_in_custody():
    the_sets = _sets()
    policies, material = _registered(
        the_sets, threshold=2.5
    )  # good_serve is off by exactly 2 U
    result, capture = _measure(the_sets, policies, material)
    assert result["gates"][pool_exam.ACCURACY_GATE] is True
    assert list(result["gates"])[-1] == pool_exam.ACCURACY_GATE
    record = result["pool"]["accuracy"]
    assert record is capture["accuracy"] and record["gate"]["passed"] is True
    inr = [r for r in record["rows"] if r["range"] == "in"]
    assert {r["output"] for r in inr} == {"f", "g"}
    assert all(
        r["n"] == 16 and r["median"] == pytest.approx(2.0) for r in inr
    )  # 8 reserved points x 2 sets
    assert result["D"] > 0
    shown = pool_exam.public(result)
    assert shown == {"status": "SCORED", "gates": [], "reasons": shown["reasons"]}
    assert "accuracy" not in json.dumps(shown) and "median" not in json.dumps(shown)


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_model_failing_the_in_range_gate_gets_no_score_and_only_the_gate_name_leaves():
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=1.5)
    result, capture = _measure(the_sets, policies, material)
    assert result["gates"][pool_exam.ACCURACY_GATE] is False and result["D"] == 0.0
    assert (
        capture["accuracy"]["gate"]["passed"] is False
    )  # the full data is still recorded
    assert pool_exam.public(result)["gates"] == [pool_exam.ACCURACY_GATE]


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_family_value_enters_a_in_a_gens_place(monkeypatch):
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=2.5)
    seen = []
    real = pps.family_value
    monkeypatch.setattr(pps, "family_value", lambda *a: seen.append(a) or real(*a))
    _measure(the_sets, policies, material)
    assert len(seen) >= len(the_sets)  # once per set at least
    assert all(
        {s.target_id for s in a[0]} <= {t.target_id for g in the_sets for t in g}
        for a in seen
    )


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_physics_material_without_a_rule_or_a_rule_without_material_refuses():
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=2.5)
    with pytest.raises(pool_exam.ExamRefused, match="scoring_cells_not_registered"):
        _measure(the_sets, dataclasses.replace(policies, physics=None), material)
    with pytest.raises(pool_exam.ExamRefused, match="scoring_cells_missing"):
        _measure(the_sets, policies, {**material, "scoring_cells": None})
    human = dataclasses.replace(policies, physics=rule(threshold=None))
    with pytest.raises(pool_exam.ExamRefused, match="threshold_is_human_input"):
        _measure(the_sets, human, material)


def test_without_a_physics_rule_the_official_grade_is_unchanged():
    plain = grade()
    explicit = pool_exam.measure_pool(**_plain_kwargs(), scoring_cells=None)
    assert plain == explicit
    assert pool_exam.ACCURACY_GATE not in plain["gates"]
    assert "accuracy" not in plain["pool"]


def _plain_kwargs():
    from test_pool_exam import sets as plain_sets

    the_sets = plain_sets()
    rows = exam_rows(the_sets)
    outputs = good_serve([r["inputs"] for r in rows])
    return {
        "binding": toy_binding(),
        "sets": the_sets,
        "policies": POLICIES,
        "bank_rows": rows,
        "outputs": outputs,
        "repeats": [outputs, outputs],
        "base_measure": fake_measure,
        "base_arguments": ARGUMENTS,
        "speed_call_seconds": FAST,
        "ceiling_seconds": CEILING,
    }


# ---------------------------------------------------------------- leakage: the record has no reader outside custody


def test_no_module_outside_the_grade_reads_the_accuracy_record():
    """The record is written by `pool_exam` (custody) and read by nothing that builds TRAIN, a kit, a view, the board or
    a miner report: the only modules naming it are the ones that make it."""
    found = sorted(
        path.relative_to(REPOSITORY).as_posix()
        for root in ("carbon", "scripts")
        for path in (REPOSITORY / root).rglob("*.py")
        if any(
            word in path.read_text(encoding="utf-8", errors="replace")
            for word in ("accuracy-record", "pool_physics_score")
        )
    )
    assert found == [
        "carbon/challenge_validator/exam_rotation.py",  # the custody sidecar's name only
        "carbon/scoring/pool_exam.py",
        "carbon/scoring/pool_exam_se.py",  # hands the record to the custody sidecar writer
        "carbon/scoring/pool_physics_score.py",
        "carbon/scoring/pool_proof_suite.py",
        "carbon/scoring/pool_version.py",  # reads the registered rule (host-only constants)
    ]


def test_the_grades_accuracy_record_reaches_the_custody_sidecar_report_even_when_gated(
    monkeypatch,
):
    """`pool_exam_se` (operator evidence, beside the private binding) hands the record to the retention writer, which
    writes ``accuracy-record.json`` once; a version without physics scoring hands nothing (no sidecar).
    """
    from carbon.development_session import single_call_timing
    from carbon.scoring import physical_dual_pack, pool_exam_se

    record = {
        "schema": pps.RECORD_SCHEMA,
        "rows": [],
        "gate": {"statistic": "p90", "passed": False},
    }

    def inputs(adapter, **kw):
        return {
            "refused": lambda code: RuntimeError(code),
            "roles": {"important_limit_definition": None, "design_objective": None},
            "n": 0,
            "width": 1,
            "values": [],
            "repeats": [[], []],
            "definition": {},
            "train_raw": b"",
        }

    monkeypatch.setattr(physical_dual_pack, "_inputs", inputs)
    monkeypatch.setattr(physical_dual_pack, "bank_rows", lambda bank, names: [])
    monkeypatch.setattr(single_call_timing, "read_side_file", lambda raw: ([0.1], True))
    for with_physics in (True, False):

        def measure(*, capture, with_physics=with_physics, **kw):
            capture["se_basis"] = {"gated": True}
            if with_physics:
                capture["accuracy"] = record

        adapter = SimpleNamespace(measure=measure, Refused=RuntimeError)
        report = {}
        with pytest.raises(RuntimeError):  # gated: the SE refuses
            pool_exam_se.bootstrap_total_se(
                adapter,
                selected=None,
                public_root=None,
                private_root=None,
                entry=None,
                job=None,
                registration=None,
                references=None,
                originals={},
                source_raw=None,
                bank=None,
                interface_names=(),
                exam_key="k",
                report=report,
            )
        assert report.get("accuracy") == (record if with_physics else None)


# ---------------------------------------------------------------- registration (pool_constants.json)


def test_the_physics_rule_registers_with_no_default(tmp_path):
    from carbon.scoring import pool_version

    document = json.loads(pool_version.CONSTANTS.read_bytes())
    base = json.loads(json.dumps(document["versions"]["chip-cold-plate 1.6"]))
    path = tmp_path / "pool_constants.json"

    def read(physics):
        entry = dict(base) if physics is None else {**base, "physics": physics}
        path.write_text(json.dumps({**document, "versions": {"fixture 9.9": entry}}))
        return pool_version.registered_policies("fixture", "9.9", path=path)

    assert read(None).physics is None  # absent: every registered version, unchanged
    good = {
        "cells_sha256": pps.cell_map(CELLS).sha256,
        "gate_statistic": "p90",
        "gate_threshold": {"f": 1.0, "g": 2.0},
        "enters": "a_gen",
    }
    rule_read = read(good).physics
    assert rule_read == pps.PhysicsRule(**good) and rule_read.cells is None
    for key in ("gate_statistic", "gate_threshold"):
        for placeholder in (pool_version.HUMAN_INPUT, None):
            with pytest.raises(pool_version.PoolConstantsNotRegistered):
                read({**good, key: placeholder})
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        read({**good, "gate_threshold": {"f": pool_version.HUMAN_INPUT}})
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        read({**good, "enters": "replace_a"})
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        read({k: v for k, v in good.items() if k != "enters"})
    assert pool_version.SCORING_CELLS in pool_version._OPTIONAL_MATERIAL_KEYS

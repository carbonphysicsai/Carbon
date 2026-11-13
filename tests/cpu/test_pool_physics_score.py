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
import math
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


def rule(
    statistic="p90",
    threshold=1.0,
    cells=CELLS,
    enters="a",
    gate_cases="agen",
    ad_split=0.5,
    total_rule="half_a_half_d",
    cell_scale="agen_scales",
):
    return pps.PhysicsRule(
        total_rule=total_rule,
        cell_scale=cell_scale,
        cells_sha256=pps.cell_map(cells).sha256,
        gate_statistic=statistic,
        gate_cases=gate_cases,
        ad_split=ad_split,
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
        ({"enters": "a_gen"}, "physics_enters_must_be_a"),
        ({"gate_cases": None}, "accuracy_gate_cases_not_registered"),
        ({"gate_cases": "train"}, "gate_cases_must_be_agen_or_pool"),
        ({"ad_split": None}, "ad_split_must_be_the_owner_set_half"),
        ({"ad_split": 0.6}, "ad_split_must_be_the_owner_set_half"),
        ({"total_rule": None}, "physics_total_rule_not_registered"),
        ({"total_rule": "d_only"}, "total_rule_must_be_half_a_half_d_or_a_only"),
        ({"cell_scale": None}, "cell_scale_not_registered"),
        ({"cell_scale": "u"}, "cell_scale_must_be"),
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


def _sets(per_class=1):
    return tuple(
        tuple(
            target
            for k in range(per_class)
            for target in (
                exam_target(f"in{s}k{k}", 30 + s + 100 * k),
                exam_target(f"edge{s}k{k}", 40 + s + 100 * k, shell=SHELL),
                exam_target(f"step{s}k{k}", 50 + s + 100 * k, shell=SHELL),
            )
        )
        for s in range(2)
    )


def _registered(the_sets, threshold):
    targets = {
        t.target_id: {"in": IN, "edge": EDGE, "step": STEP}[
            t.target_id.split("k")[0].rstrip("0123456789")
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


def _measure(the_sets, policies, material, serve=good_serve, extra_pool_inputs=()):
    rows = exam_rows(the_sets)
    # pool rows no target holds (the in-range case set's rows, which the pack adds to the pool: `pool_version`)
    rows += [
        {
            "case_id": f"extra:{i}",
            "inputs": dict(inputs),
            "reference": None,
            "cohort": pool_exam.POOL_COHORT,
        }
        for i, inputs in enumerate(extra_pool_inputs)
    ]
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
def test_a_is_the_family_value_and_the_in_range_a_leg_leaves_the_score(monkeypatch):
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=2.5)
    seen = []
    real = pps.family_value

    def recording(*a):
        value = real(*a)
        seen.append(({s.target_id for s in a[0]}, value))
        return value

    monkeypatch.setattr(pps, "family_value", recording)
    result, _capture = _measure(the_sets, policies, material)
    per_set = {
        frozenset(ids): value for ids, value in seen
    }  # the official loop's calls
    expected = statistics.fmean(
        per_set[frozenset(t.target_id for t in group)] for group in the_sets
    )
    assert result["A"] == pytest.approx(expected, abs=1e-15)

    # the sealed grader's in-range A leg never moves A: a different base A gives the same A
    original = fake_measure

    def other_base(**kw):
        measured = original(**kw)
        return {**measured, "A": 0.123, "A_legs": {}}

    monkeypatch.setattr(sys.modules[__name__], "fake_measure", other_base)
    again, _ = _measure(the_sets, policies, material)
    assert again["A"] == result["A"]


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_pool_gate_cases_read_every_kept_point_of_the_in_range_targets():
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=2.5)
    pooled = dataclasses.replace(
        policies, physics=dataclasses.replace(policies.physics, gate_cases="pool")
    )
    result, _capture = _measure(the_sets, pooled, material)
    record = result["pool"]["accuracy"]
    kept = sum(len(g[0].designs) for g in the_sets)  # the in-range target of each set
    assert all(r["n"] == kept for r in record["rows"] if r["range"] == "in")
    # out-of-range rows stay on the reserved slices
    assert all(r["n"] == 16 for r in record["rows"] if r["range"] == "out")


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_target_bootstrap_recomposes_the_physics_total_exactly():
    the_sets = _sets(per_class=2)  # 6 targets per set (the SE needs at least 4)
    policies, material = _registered(the_sets, threshold=2.5)
    result, capture = _measure(the_sets, policies, material)
    basis = capture["se_basis"]
    assert basis["physics"] is True
    graded = 0.5 * result["A"] + 0.5 * result["D"]
    assert basis["total"] == pytest.approx(graded, abs=1e-15)
    # no resampling: the recomposed total is the graded one
    assert pool_exam.total_of_targets(basis, basis["sets"]) == pytest.approx(
        graded, abs=1e-15
    )
    spread, sizes = pool_exam.target_bootstrap_se(basis, "sha256:" + "ab" * 32)
    assert sizes == [6, 6] and math.isfinite(spread) and spread >= 0.0
    # deterministic in the exam key
    assert pool_exam.target_bootstrap_se(basis, "sha256:" + "ab" * 32)[0] == spread


def test_a_tightened_cell_scale_applies_the_registered_a_multiplier():
    specs, plan = stand_set()
    scales = {"f": 0.5, "g": 0.5}
    plain = attached(specs, plan)
    tight = dataclasses.replace(
        attached(specs, plan, cell_scale="agen_scales_x_a_multiplier"), a_multiplier=2.0
    )
    edge = statistics.fmean([benefit(2 * 0.5 / 0.5), benefit(2 * 1.5 / 0.5)])
    expected = statistics.fmean([edge, benefit(2 * 1.0 / 0.5)])
    got = pps.family_value(specs, model(specs), scales, plan, tight)
    assert got == pytest.approx(expected, abs=1e-15)
    assert got < pps.family_value(specs, model(specs), scales, plan, plain)
    unattached = dataclasses.replace(tight, a_multiplier=None)
    with pytest.raises(pps.PhysicsRefused, match="needs_the_registered_a_multiplier"):
        pps.family_value(specs, model(specs), scales, plan, unattached)


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
        "scripts/dev/headroom_admission.py",  # the TL's custody writer of the admission file
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
        "gate_cases": "pool",
        "enters": "a",
        "ad_split": 0.5,
        "total_rule": "half_a_half_d",
        "cell_scale": "agen_scales",
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
        read({**good, "enters": "a_gen"})
    for key, value in (
        ("ad_split", pool_version.HUMAN_INPUT),
        ("ad_split", 0.6),
        ("total_rule", pool_version.HUMAN_INPUT),
        ("total_rule", "d_only"),
        ("cell_scale", pool_version.HUMAN_INPUT),
    ):
        with pytest.raises(pool_version.PoolConstantsNotRegistered):
            read({**good, key: value})
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        read({k: v for k, v in good.items() if k != "enters"})
    with_cases = {**good, "in_range_cases_sha256": "c" * 64}
    assert read(with_cases).physics.in_range_cases_sha256 == "c" * 64
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        read({**good, "in_range_cases_sha256": "not-hex"})
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        read({**good, "unknown": 1})
    assert pool_version.SCORING_CELLS in pool_version._OPTIONAL_MATERIAL_KEYS
    assert pool_version.IN_RANGE_CASES in pool_version._OPTIONAL_MATERIAL_KEYS


# ---------------------------------------------------------------- the in-range case set (truths outside the pool targets)

PRIMARY = "fixture:primary"


def _case_document(the_sets, count=6, name=PRIMARY):
    """In-range cases read from rows the model answers (here: the in-range targets' pool rows, standing in for a
    version's in-box non-TRAIN primaries), with their true outputs and U."""
    from test_pool_plugin import U, truth

    cases = []
    for group in the_sets:
        spec = group[0]  # the in-range target of each set
        for design in spec.designs[:count]:
            row = {"cond": 1.0, "x": design[0], "y": design[1]}
            f, g = truth(row)
            cases.append(
                {
                    "class": name,
                    "inputs": row,
                    "truths": {"f": f, "g": g},
                    "u": {"f": U, "g": U},
                }
            )
    return {"schema": pps.IN_RANGE_CASES_SCHEMA, "cases": cases}


def _with_cases(policies, material, document):
    digest = pps.in_range_cases(document).sha256
    physics = dataclasses.replace(policies.physics, in_range_cases_sha256=digest)
    return dataclasses.replace(policies, physics=physics), {
        **material,
        "in_range_cases": document,
    }


@pytest.mark.parametrize(
    "mutate, code",
    [
        (lambda d: d.update(schema="x"), "in_range_cases_malformed"),
        (lambda d: d.update(cases=[]), "in_range_cases_malformed"),
        (lambda d: d["cases"][0]["u"].update(f=0.0), "in_range_case_malformed"),
        (lambda d: d["cases"][0]["truths"].pop("g"), "in_range_case_malformed"),
        (lambda d: d["cases"][0].update(extra=1), "in_range_case_malformed"),
    ],
)
def test_the_in_range_case_set_refuses_a_malformed_document(mutate, code):
    document = _case_document(_sets())
    mutate(document)
    with pytest.raises(pps.PhysicsRefused, match=code):
        pps.in_range_cases(document)


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_registered_in_range_cases_are_recorded_and_gated_never_scored():
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=2.5)
    plain, _ = _measure(the_sets, policies, material)
    policies, material = _with_cases(policies, material, _case_document(the_sets))
    result, _capture = _measure(the_sets, policies, material)
    rows = [r for r in result["pool"]["accuracy"]["rows"] if r["class"] == PRIMARY]
    assert {r["output"] for r in rows} == {"f", "g"}
    assert all(
        r["range"] == "in"
        and r["n"] == 12
        and r["median"] == pytest.approx(2.0)
        and r["n_invalid"] == 0
        and r["verdict"] == "PASS"
        and r["scored"] is False
        and r["family"] is None
        for r in rows
    )
    assert result["gates"][pool_exam.ACCURACY_GATE] is True
    assert (result["A"], result["D"]) == (plain["A"], plain["D"])  # never scored
    tight = dataclasses.replace(
        policies, physics=dataclasses.replace(policies.physics, gate_threshold=1.5)
    )
    failed, _ = _measure(the_sets, tight, material)
    assert failed["gates"][pool_exam.ACCURACY_GATE] is False and failed["D"] == 0.0


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_an_invalid_answer_on_a_case_fails_the_gate_typed():
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=2.5)
    policies, material = _with_cases(policies, material, _case_document(the_sets))
    plan = coverage_plan(material["coverage_plan"])
    attached_rule = pps.attach_cells(
        policies.physics, CELLS, plan, the_sets, material["in_range_cases"]
    )
    record = pps.accuracy_record(
        [s for g in the_sets for s in g],
        lambda c, d: [{"f": 0.0, "g": 0.0} for _ in d],
        plan,
        attached_rule,
        lambda rows: [None] * len(rows),
    )
    rows = [r for r in record["rows"] if r["class"] == PRIMARY]
    assert all(r["n_invalid"] == 12 and r["verdict"] == "FAIL" for r in rows)
    assert record["gate"]["passed"] is False


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_case_set_structure_is_refused_before_any_grade():
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=2.5)
    document = _case_document(the_sets)
    with_cases, with_material = _with_cases(policies, material, document)
    with pytest.raises(pool_exam.ExamRefused, match="in_range_cases_not_registered"):
        _measure(the_sets, policies, {**material, "in_range_cases": document})
    with pytest.raises(pool_exam.ExamRefused, match="in_range_cases_missing"):
        _measure(the_sets, with_cases, material)
    other = _case_document(the_sets, count=3)
    with pytest.raises(pool_exam.ExamRefused, match="in_range_cases_sha256_mismatch"):
        _measure(the_sets, with_cases, {**with_material, "in_range_cases": other})
    out_of_range = _case_document(the_sets, name=EDGE)
    oor_policies, oor_material = _with_cases(policies, material, out_of_range)
    with pytest.raises(pool_exam.ExamRefused, match="case_class_is_out_of_range"):
        _measure(the_sets, oor_policies, oor_material)
    stray = _case_document(the_sets)
    stray["cases"][0]["inputs"] = {"cond": 1.0, "x": 0.123456, "y": 0.654321}
    stray_policies, stray_material = _with_cases(policies, material, stray)
    with pytest.raises(pool_exam.ExamRefused, match="in_range_case_not_an_exam_row"):
        _measure(the_sets, stray_policies, stray_material)


def test_a_version_with_no_in_range_case_at_all_refuses():
    specs, _plan = stand_set()
    out_only = [s for s in specs if s.extended]
    plan = coverage_plan(
        plan_document(
            [EDGE, STEP, "fixture:extra"],
            {"e0": EDGE, "s0": STEP, "x0": "fixture:extra"},
        )
    )
    with pytest.raises(
        pps.PhysicsRefused, match="accuracy_gate_without_in_range_cases"
    ):
        pps.attach_cells(rule(), CELLS, plan, (tuple(out_only),))


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_only_total_is_the_physics_score_alone_and_the_se_recomposes_it():
    """The owner's per-version pick for a version whose D does not separate: TOTAL = A. The dual pack's 0.5 A + 0.5 D
    stays the composition, with D reported as A, so the total is exactly A."""
    the_sets = _sets(per_class=2)
    policies, material = _registered(the_sets, threshold=2.5)
    half, _ = _measure(the_sets, policies, material)
    alone = dataclasses.replace(
        policies, physics=dataclasses.replace(policies.physics, total_rule="a_only")
    )
    result, capture = _measure(the_sets, alone, material)
    assert result["A"] == half["A"] and result["D"] == result["A"]
    assert result["pool"]["total_rule"] == "a_only"
    assert "total_rule" not in half["pool"]
    basis = capture["se_basis"]
    assert basis["a_only"] is True
    assert pool_exam.total_of_targets(basis, basis["sets"]) == pytest.approx(
        result["A"], abs=1e-15
    )
    spread, _sizes = pool_exam.target_bootstrap_se(basis, "sha256:" + "cd" * 32)
    assert math.isfinite(spread)


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_record_carries_the_sealed_graders_measured_laws_every_grade(monkeypatch):
    """Validator 5 Nov (condition before FINAL): laws measured but not yet given a gate margin are recorded per grade
    in the custody accuracy record, never scored (A is the family value)."""
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=2.5)
    half = {
        "mean_residual_by_law": {"fixture_affine": 0.25, "fixture_zero_current": 0.5},
        "mean_residual": 0.375,
        "mean_response_error": 0.1,
        "sign_gate_failed": [],
        "gate_failed_laws": [],
    }
    plain, _ = _measure(
        the_sets, policies, material
    )  # the same model, no laws reported
    original = fake_measure

    def with_laws(**kw):
        return {**original(**kw), "physics_half": half}

    monkeypatch.setattr(sys.modules[__name__], "fake_measure", with_laws)
    result, capture = _measure(the_sets, policies, material)
    laws = result["pool"]["accuracy"]["laws"]
    assert laws["physics_half"] == half and laws["physics_half"] is not half
    assert set(laws["a_legs"]) == {"A_acc", "A_robust", "A_law", "A_response"}
    assert capture["accuracy"]["laws"] == laws
    assert result["A"] == plain["A"]  # never scored
    # a gated model still records them
    tight = dataclasses.replace(
        policies, physics=dataclasses.replace(policies.physics, gate_threshold=1.5)
    )
    failed, _ = _measure(the_sets, tight, material)
    assert failed["pool"]["accuracy"]["laws"]["physics_half"] == half
    assert "laws" not in json.dumps(pool_exam.public(result))


def _cases_outside_the_pool_targets(the_sets, count=6):
    """The in-range case set as a real version registers it: in-box rows that are NOT any target's pool design."""
    from test_pool_plugin import U, truth

    document = _case_document(the_sets, count=count)
    for k, case in enumerate(document["cases"]):
        row = {"cond": 1.0, "x": 0.111 + 0.0137 * k, "y": 0.222 + 0.0071 * k}
        f, g = truth(row)
        case.update(inputs=row, truths={"f": f, "g": g}, u={"f": U, "g": U})
    held = {
        (r["inputs"]["cond"], r["inputs"]["x"], r["inputs"]["y"])
        for r in exam_rows(the_sets)
    }
    assert not any(
        (c["inputs"]["cond"], c["inputs"]["x"], c["inputs"]["y"]) in held
        for c in document["cases"]
    )
    return document


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_in_range_cases_outside_the_pool_targets_are_graded_when_the_pack_carries_their_rows():
    """Canary 3 (13 Nov): a 1.8-style in-range case set (rows no target holds) refused every grade as
    in_range_case_not_an_exam_row because the bank never held its rows. With the rows in the pool (the pack adds
    them), the grade reads each answer from the model's one table and the gate is computed.
    """
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=2.5)
    document = _cases_outside_the_pool_targets(the_sets)
    policies, material = _with_cases(policies, material, document)
    extra = [c["inputs"] for c in document["cases"]]
    result, _ = _measure(the_sets, policies, material, extra_pool_inputs=extra)
    assert result["gates"][pool_exam.ACCURACY_GATE] is True
    assert result["D"] > 0
    # The case rows are answered pool rows and nothing more: they never score or enter any target's pool (CV-Motor-C
    # decides if they ever should). The same exam without the case set grades the same A, D and gates.
    plain_policies, plain_material = _registered(the_sets, threshold=2.5)
    plain, _ = _measure(the_sets, plain_policies, plain_material)
    assert (result["A"], result["D"]) == (plain["A"], plain["D"])
    assert result["gates"] == plain["gates"]
    # the rows are what the pack must add: without them the grade names the missing row, as before
    with pytest.raises(pool_exam.ExamRefused, match="in_range_case_not_an_exam_row"):
        _measure(the_sets, policies, material)
    # and a pool row that is no target's, no menu's and no case's is still refused
    with pytest.raises(
        pool_exam.ExamRefused, match="exam_pool_rows_differ_from_the_targets_pools"
    ):
        _measure(
            the_sets,
            policies,
            material,
            extra_pool_inputs=[*extra, {"cond": 1.0, "x": 0.9, "y": 0.9}],
        )

"""Typed-state outputs on the pool path (BT 3.2 rule bt32-threshold-recovery-two-part.v1, spec line rev 3 8d812755).

Claims:
1. A target without typed truths, a rule without typed outputs and an admission cell without ``m_anchor`` are read
   exactly as before (identity, digest and every grade path unchanged; the existing pool suites are the wider proof).
2. A target carries typed truths beside its outputs, inside its identity, round-tripping through dump / load; the D
   part's validity ignores their keys.
3. The headroom grader scores a typed cell by the rule (EVENT / VALUE / coverage, S5 combination) from pooled sums, so
   the target bootstrap recomposes it; the in-range gate reads only both-value cases (S7).
4. The registration has no default: a null or HUMAN_INPUT in a typed output refuses.

Every class, anchor, threshold and U here is a SYNTHETIC fixture.
"""

from __future__ import annotations

import dataclasses
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_pool_multiclass_regions import plan_document

from carbon.scoring import (
    pool_grader,
    pool_version,
)
from carbon.scoring import pool_physics_score as pps
from carbon.scoring import typed_state_output as tso

IN, EDGE = "fixture:in", "fixture:edge"
PASS = dict.fromkeys(pps.ADMISSION_TESTS, "PASS")
REC = tso.TypedOutput("rec", "recovery", tso.RULE_ID, 85.0, "peak", 0.5, 2.0, 0.5)
PLAN = pool_grader.coverage_plan(plan_document([IN, EDGE], {"i0": IN, "e0": EDGE}))


def target(target_id, extended, rows):
    """``rows`` = [(peak truth, rec truth, peak prediction, rec prediction), ...]; peak U 0.5."""
    return SimpleNamespace(
        target_id=target_id,
        extended=extended,
        agen=tuple(range(len(rows))),
        outputs=("peak",),
        conditions={"case": target_id},
        designs=tuple((float(i),) for i in range(len(rows))),
        truths=tuple({"peak": r[0]} for r in rows),
        typed_truths=tuple({"rec": r[1]} for r in rows),
        u_at=lambda index, name: 0.5,
        answers=tuple({"peak": r[2], "rec": r[3]} for r in rows),
    )


def model(specs):
    by_case = {s.target_id: s.answers for s in specs}

    def predict(conditions, designs):
        return [dict(by_case[conditions["case"]][int(d[0])]) for d in designs]

    return predict


IN_ROWS = [(90.0, 10.0, 90.0, 10.0), (80.0, "NEVER_REACHED", 80.0, "NEVER_REACHED")]
EDGE_ROWS = [
    (90.0, 10.0, 90.0, 14.0),  # both value: |err| = 4 = 2 U
    (
        90.0,
        20.0,
        90.0,
        "NOT_RECOVERED",
    ),  # resolvable value called empty: event miss, in T not B
    (80.0, "NEVER_REACHED", 80.0, "NEVER_REACHED"),  # right state
    (85.2, "NEVER_REACHED", 85.2, "NOT_RECOVERED"),  # band: wrong state, never counted
]


def doc(m_anchor=2, tests=None):
    return {
        "schema": pps.HEADROOM_SCHEMA,
        "families": {"fixture-F1": [EDGE]},
        "cells": [
            {
                "family": "fixture-F1",
                "class": EDGE,
                "output": "peak",
                "anchor_u": 8.0,
                "anchor_lo_u": 8.0,
                "n": 4,
                "tests": dict(PASS),
            },
            {
                "family": "fixture-F1",
                "class": EDGE,
                "output": "rec",
                "anchor_u": 8.0,
                "anchor_lo_u": 8.0,
                "n": 4,
                "tests": dict(PASS if tests is None else tests),
                "m_anchor": m_anchor,
            },
        ],
    }


def rule(document, *, typed=(REC,)):
    base = pps.PhysicsRule(
        cells_sha256="0" * 64,
        gate_statistic="max",
        gate_threshold=3.0,
        gate_cases="agen",
        enters="a",
        ad_split=0.5,
        total_rule="half_a_half_d",
        cell_scale=None,
        scoring="headroom",
        skill_form="log",
        h_min=4.0,
        h_lo=2.5,
        n_min=1,
        typed_outputs=typed,
    )
    return dataclasses.replace(
        base, cells_sha256=pps.headroom_admission(document, base).sha256
    )


def specs():
    return [target("i0", False, IN_ROWS), target("e0", True, EDGE_ROWS)]


def attach(document=None, **kw):
    document = doc() if document is None else document
    s = specs()
    return s, pps.attach_cells(rule(document, **kw), document, PLAN, (tuple(s),))


# ---------------------------------------------------------------- 1. untouched without typed outputs


def test_a_rule_without_typed_outputs_is_unchanged_and_refuses_a_typed_cell():
    plain = dataclasses.replace(rule(doc()), typed_outputs=None)
    pps.check_rule(plain)
    with pytest.raises(pps.PhysicsRefused, match="headroom_admission_cell_malformed"):
        pps.headroom_admission(
            doc(), plain
        )  # an m_anchor on a non-typed output is malformed


def test_typed_outputs_need_headroom_and_a_complete_registration():
    with pytest.raises(pps.PhysicsRefused, match="typed_outputs_need_headroom_scoring"):
        pps.check_rule(
            dataclasses.replace(
                rule(doc()),
                scoring="cells",
                skill_form=None,
                h_min=None,
                h_lo=None,
                n_min=None,
                cell_scale="agen_scales",
            )
        )
    with pytest.raises(pps.PhysicsRefused, match="value_u_is_human_input"):
        pps.check_rule(
            dataclasses.replace(
                rule(doc()), typed_outputs=(dataclasses.replace(REC, value_u=None),)
            )
        )
    with pytest.raises(pps.PhysicsRefused, match="typed_outputs_duplicate_output"):
        pps.check_rule(dataclasses.replace(rule(doc()), typed_outputs=(REC, REC)))


# ---------------------------------------------------------------- 2. the target's identity and the D view


def _pool(typed=None, **kw):
    designs = [[0.1 * i] for i in range(6)]
    truths = [{"y": float(i)} for i in range(6)]
    return pool_grader.build_target(
        target_id="t",
        conditions={"fixed": {}},
        outputs=("y",),
        objective="y",
        sense="max",
        limits=(),
        u={"y": 0.1},
        box=((0.0, 1.0),),
        designs=designs,
        truths=truths,
        agen=(5,),
        start=(0.5,),
        seed=1,
        typed_truths=typed,
        **kw,
    )


def test_a_target_without_typed_truths_keeps_its_digest():
    plain = _pool()
    assert plain.typed_truths == () and plain.typed_outputs() == ()
    assert "typed_truths" not in pool_grader.dump_pool(plain)
    assert pool_grader.core_prediction({"y": 1.0, "rec": 2.0}, plain) == {
        "y": 1.0,
        "rec": 2.0,
    }


def test_typed_truths_enter_the_identity_and_round_trip():
    typed = {"rec": [1.0, "NEVER_REACHED", 3.0, "NOT_RECOVERED", 5.0, 6.0]}
    spec = _pool(typed)
    assert spec.typed_outputs() == ("rec",)
    assert spec.digest != _pool().digest
    document = json.loads(json.dumps(pool_grader.dump_pool(spec)))
    again = pool_grader.load_pool(document)
    assert again.digest == spec.digest and again.typed_truths == spec.typed_truths
    assert pool_grader.core_prediction({"y": 1.0, "rec": "NEVER_REACHED"}, spec) == {
        "y": 1.0
    }


@pytest.mark.parametrize(
    "typed, code",
    [
        (
            {"y": [1.0] * 6},
            "typed_truths_must_name_new_outputs_per_design",
        ),  # collides with an output
        (
            {"rec": [1.0] * 5},
            "typed_truths_must_name_new_outputs_per_design",
        ),  # one per design
        ({"rec": [1.0] * 5 + [None]}, "typed_truth_must_be_a_number_or_a_state_token"),
        ({"rec": [1.0] * 5 + [-1.0]}, "typed_truth_must_be_a_number_or_a_state_token"),
    ],
)
def test_typed_truths_are_validated(typed, code):
    with pytest.raises(pool_grader.PoolRefused, match=code):
        _pool(typed)


# ---------------------------------------------------------------- 3. the grade


def test_the_typed_cell_scores_by_the_rule_and_recomposes_from_sums():
    s, attached = attach()
    e0 = s[1]
    expected_sums = tso.cell_sums(REC, [(r[1], r[3], r[0]) for r in EDGE_ROWS])
    assert expected_sums == (
        1,
        3,
        math.log(2.0),
        1,
        2,
    )  # one resolvable miss (the band miss is not counted); B 1, T 2
    cells = pps.target_cells(e0, model(s), {}, PLAN, attached)
    key = ("fixture-F1", EDGE, "rec")
    assert cells[key] == (expected_sums, 4)
    typed_value = tso.combine(REC, expected_sums, m_anchor=2, value_anchor=8.0)
    assert typed_value == pytest.approx(
        0.5 * (1 - 1 / 2) + 0.5 * (math.log(8 / 2) / math.log(8)) * 1 / 2
    )
    peak_value = pps.skill(attached, 8.0, 1.0)  # peak errors 0: floored at 1 U
    got = pps.family_value(s, model(s), {}, PLAN, attached)
    assert got == pytest.approx((peak_value + typed_value) / 2)
    assert pps.compose([cells], attached) == pytest.approx(got)


def test_event_only_and_unscored_typed_cells():
    s, attached = attach(
        doc(m_anchor=2, tests={**PASS, "H": "FAIL"})
    )  # VALUE tests fail: EVENT part alone
    assert attached.cells.typed_anchor(("fixture-F1", EDGE, "rec")) == (2, None, 3)
    peak_value = pps.skill(attached, 8.0, 1.0)
    got = pps.family_value(s, model(s), {}, PLAN, attached)
    assert got == pytest.approx((peak_value + (1 - 1 / 2)) / 2)
    # neither part admitted for the cell: report-only, the family is the peak cell alone
    s, attached = attach(doc(m_anchor=0, tests={**PASS, "H": "FAIL"}))
    assert ("fixture-F1", EDGE, "rec") in attached.cells.not_admitted
    assert pps.family_value(s, model(s), {}, PLAN, attached) == pytest.approx(
        peak_value
    )


def test_the_gate_reads_only_both_value_cases():
    s, attached = attach()
    record = pps.accuracy_record(s, model(s), PLAN, attached)
    rows = {(r["class"], r["output"]): r for r in record["rows"]}
    assert rows[(EDGE, "rec")]["n"] == 1 and rows[(EDGE, "rec")][
        "max"
    ] == pytest.approx(
        2.0
    )  # B only
    assert rows[(IN, "rec")]["n"] == 1 and rows[(IN, "rec")]["verdict"] == "PASS"
    assert record["gate"]["passed"] is True
    # an in-range state mismatch moves nothing in the gate (it is charged in the EVENT part)
    mismatch = [
        target("i0", False, [IN_ROWS[0], (80.0, "NEVER_REACHED", 80.0, 3.0)]),
        s[1],
    ]
    again = pps.accuracy_record(mismatch, model(mismatch), PLAN, attached)
    in_rec = next(r for r in again["rows"] if r["class"] == IN and r["output"] == "rec")
    assert (in_rec["n"], in_rec["max"], in_rec["verdict"]) == (1, 0.0, "PASS")


def test_a_missing_or_foreign_token_is_an_invalid_answer():
    s, attached = attach()
    for bad in (None, "NOT_REACHED", -1.0):
        broken = [s[0], target("e0", True, [EDGE_ROWS[0][:3] + (bad,)] + EDGE_ROWS[1:])]
        with pytest.raises(pps.PhysicsRefused, match="agen_prediction_invalid"):
            pps.target_cells(broken[1], model(broken), {}, PLAN, attached)
    missing = SimpleNamespace(
        **{**vars(s[1]), "answers": tuple({"peak": r[2]} for r in EDGE_ROWS)}
    )
    with pytest.raises(pps.PhysicsRefused, match="agen_prediction_invalid"):
        pps.target_cells(missing, model([s[0], missing]), {}, PLAN, attached)


def test_an_unregistered_typed_output_on_a_target_refuses():
    s = specs()
    other = SimpleNamespace(
        **{**vars(s[1]), "typed_truths": tuple({"other": r[1]} for r in EDGE_ROWS)}
    )
    with pytest.raises(
        pps.PhysicsRefused,
        match="typed_outputs_must_be_exactly_the_registered_ones_on_every_target",
    ):
        pps.attach_cells(rule(doc()), doc(), PLAN, ((s[0], other),))


# ---------------------------------------------------------------- 4. the registration


def _registration(**typed_fields):
    entry = {
        "output": "rec",
        "kind": "recovery",
        "rule": tso.RULE_ID,
        "threshold_c": 85.0,
        "band_output": "peak",
        "band_u": 0.5,
        "value_u": 2.0,
        "event_weight": 0.5,
        **typed_fields,
    }
    return {
        "cells_sha256": "0" * 64,
        "gate_statistic": "max",
        "gate_threshold": 3.0,
        "gate_cases": "agen",
        "enters": "a",
        "ad_split": 0.5,
        "total_rule": "half_a_half_d",
        "scoring": "headroom",
        "skill_form": "log",
        "h_min": 4.0,
        "h_lo": 2.5,
        "n_min": 1,
        "typed_outputs": [entry],
    }


def test_the_registration_parses_typed_outputs_with_no_default():
    parsed = pool_version._physics(_registration())
    assert parsed.typed_outputs == (REC,)
    for field in ("value_u", "band_u", "threshold_c", "event_weight"):
        for missing in (None, pool_version.HUMAN_INPUT):
            with pytest.raises(
                pool_version.PoolConstantsNotRegistered,
                match="pool_constants_not_registered",
            ):
                pool_version._physics(_registration(**{field: missing}))
    bad = _registration()
    bad["typed_outputs"][0]["extra"] = 1
    with pytest.raises(
        pool_version.PoolConstantsNotRegistered, match="pool_constants_malformed"
    ):
        pool_version._physics(bad)


# ---------------------------------------------------------------- review fixes


def test_an_in_range_class_with_no_both_value_case_adds_nothing_to_the_gate():
    s = specs()
    no_value = [
        target(
            "i0",
            False,
            [
                (80.0, "NEVER_REACHED", 80.0, "NEVER_REACHED"),
                (80.0, "NEVER_REACHED", 80.0, 3.0),
            ],
        ),
        s[1],
    ]
    attached = pps.attach_cells(rule(doc()), doc(), PLAN, (tuple(no_value),))
    record = pps.accuracy_record(no_value, model(no_value), PLAN, attached)
    in_rec = next(
        r for r in record["rows"] if r["class"] == IN and r["output"] == "rec"
    )
    assert (in_rec["n"], in_rec["verdict"]) == (0, "PASS")
    assert record["gate"]["passed"] is True


def test_a_bad_typed_answer_fails_the_validity_gate_not_the_challenge():
    s, attached = attach()
    check = pps.answer_check(attached)
    assert pps.answer_check(dataclasses.replace(attached, typed_outputs=None)) is None
    assert pool_grader.agen_predictions_valid(s, model(s), check) is True
    for bad in (None, "NOT_REACHED", -1.0, math.nan):
        broken = [s[0], target("e0", True, [EDGE_ROWS[0][:3] + (bad,)] + EDGE_ROWS[1:])]
        assert pool_grader.agen_predictions_valid(broken, model(broken), check) is False
    missing = SimpleNamespace(
        **{**vars(s[1]), "answers": tuple({"peak": r[2]} for r in EDGE_ROWS)}
    )
    assert (
        pool_grader.agen_predictions_valid(
            [s[0], missing], model([s[0], missing]), check
        )
        is False
    )


@pytest.mark.parametrize("token", ["NOT_REACHED", "never_reached", ""])
def test_an_unreadable_truth_token_is_refused_when_the_exam_is_attached(token):
    s = specs()
    rows = [EDGE_ROWS[0], (90.0, token, 90.0, "NEVER_REACHED")] + EDGE_ROWS[2:]
    with pytest.raises(pps.PhysicsRefused, match="typed_output_truth_unreadable"):
        pps.attach_cells(rule(doc()), doc(), PLAN, ((s[0], target("e0", True, rows)),))


def test_every_target_must_carry_the_registered_typed_outputs():
    s = specs()
    bare = SimpleNamespace(**{**vars(s[0]), "typed_truths": ()})
    with pytest.raises(
        pps.PhysicsRefused, match="typed_outputs_must_be_exactly_the_registered_ones"
    ):
        pps.attach_cells(rule(doc()), doc(), PLAN, ((bare, s[1]),))


def test_the_event_anchor_count_is_over_the_whole_exam():
    s = specs()
    s2 = [target("i1", False, IN_ROWS), target("e1", True, EDGE_ROWS)]
    plan = pool_grader.coverage_plan(
        plan_document([IN, EDGE], {"i0": IN, "e0": EDGE, "i1": IN, "e1": EDGE})
    )
    document = doc()
    document["cells"] = [dict(c, n=8) for c in document["cells"]]
    attached = pps.attach_cells(rule(document), document, plan, (tuple(s), tuple(s2)))
    assert attached.cells.typed_anchor(("fixture-F1", EDGE, "rec")) == (
        2,
        8.0,
        6,
    )  # 3 resolvable cases per set
    # per set: m 1 of r 3 against the anchor's 2 of 6: the same rate, so the EVENT part is 0
    cells = pps.target_cells(s[1], model(s), {}, plan, attached)
    typed_value = tso.combine(
        REC,
        cells[("fixture-F1", EDGE, "rec")][0],
        m_anchor=2,
        value_anchor=8.0,
        r_anchor=6,
    )
    assert typed_value == pytest.approx(
        0.5 * 0.0 + 0.5 * (math.log(8 / 2) / math.log(8)) * 1 / 2
    )


def test_the_admission_writer_accepts_typed_cells_only_when_named(tmp_path, capsys):
    sys.path.insert(0, str(HERE.parents[1] / "scripts" / "dev"))
    import headroom_admission as writer

    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps({k: v for k, v in doc().items() if k != "schema"}))
    args = ["--h-min", "4", "--h-lo", "2.5", "--n-min", "1"]
    refused = tmp_path / "refused.json"
    assert (
        writer.main(["write", "--draft", str(draft), "--out", str(refused), *args]) == 1
    )
    assert "headroom_admission_cell_malformed" in capsys.readouterr().out
    out = tmp_path / "admission.json"
    typed = ["--typed-output", "rec"]
    assert (
        writer.main(["write", "--draft", str(draft), "--out", str(out), *args, *typed])
        == 0
    )
    printed = json.loads(capsys.readouterr().out)
    assert printed["admitted"] == 2 and printed["sha256"] == rule(doc()).cells_sha256
    assert writer.main(["check", str(out), *args, *typed]) == 0
    assert EDGE not in capsys.readouterr().out


# ---------------------------------------------------------------- spec rev 3, check 11


def test_check_11_the_event_part_needs_a_valid_reference_and_n_min():
    base = rule(doc())
    key = ("fixture-F1", EDGE, "rec")
    # control: (V) PASS and n >= n_min, the VALUE tests failed: the EVENT part alone is admitted
    ok = pps.headroom_admission(doc(m_anchor=2, tests={**PASS, "H": "FAIL"}), base)
    assert key in ok.scored and ok.typed_anchor(key) == (2, None)
    # (V) FAIL: not admitted at all, whatever m_anchor is (the VALUE part's five tests fail too)
    v_fail = pps.headroom_admission(doc(m_anchor=2, tests={**PASS, "V": "FAIL"}), base)
    assert key in v_fail.not_admitted and key not in v_fail.scored
    # n < n_min: not admitted at all
    thin = doc(m_anchor=2, tests={**PASS, "H": "FAIL"})
    thin["cells"][-1]["n"] = 1
    thin_admission = pps.headroom_admission(thin, dataclasses.replace(base, n_min=2))
    assert key in thin_admission.not_admitted and key not in thin_admission.scored

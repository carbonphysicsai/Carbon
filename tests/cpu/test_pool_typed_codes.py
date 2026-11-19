"""BT 3.2 raw-row codes end to end (Validator-BT adapter rulings rev 2 ebc427fa (B) 5): a model's raw negative number in a typed
column is decoded by the version's derive (`tso.with_codes`) BEFORE the grade's validity check, so a row answering
-1 / -0.93 / -1.5 grades EXACTLY as one answering "NEVER_REACHED", and -1.51 / -7 exactly as "NOT_RECOVERED": the same A_gen
validity, the same family value and the same accuracy record (gate). Every class, anchor, threshold and U is a SYNTHETIC fixture
(`test_pool_typed_outputs`); only the output carries the registered name, since the code table is keyed by it.
"""

from __future__ import annotations

import dataclasses
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import test_pool_typed_outputs as T

from carbon.scoring import pool_grader
from carbon.scoring import pool_physics_score as pps
from carbon.scoring import typed_state_output as tso

NAME = "threshold_recovery_s"
R32 = dataclasses.replace(T.REC, output=NAME)
CODE = {"NEVER_REACHED": (-1.0, -0.93, -1.5), "NOT_RECOVERED": (-1.51, -7.0)}


def _doc():
    document = T.doc()
    for cell in document["cells"]:
        if cell["output"] == "rec":
            cell["output"] = NAME
    return document


def _target(target_id, extended, rows, variant):
    """``rows`` as `test_pool_typed_outputs` ([peak truth, rec truth, peak prediction, rec prediction]); ``answers`` = the token
    form, ``raw`` = the same answers as a raw model row [peak, rec] with every token written as one of its codes (``variant``
    picks which)."""
    raw = []
    for r in rows:
        p = r[3]
        raw.append([r[2], CODE[p][variant % len(CODE[p])] if type(p) is str else p])
    return SimpleNamespace(
        target_id=target_id,
        extended=extended,
        agen=tuple(range(len(rows))),
        outputs=("peak",),
        conditions={"case": target_id},
        designs=tuple((float(i),) for i in range(len(rows))),
        truths=tuple({"peak": r[0]} for r in rows),
        typed_truths=tuple({NAME: r[1]} for r in rows),
        u_at=lambda index, name: 0.5,
        answers=tuple({"peak": r[2], NAME: r[3]} for r in rows),
        raw=tuple(raw),
    )


def _base_derive(_inputs, raw):
    # a stand-in 3.2 derive: the raw row is [peak, threshold_recovery_s] (the real column order is the kit's)
    return {"peak": raw[0], NAME: raw[1]}


def _token_model(specs):
    by_case = {s.target_id: s.answers for s in specs}
    return lambda conditions, designs: [
        dict(by_case[conditions["case"]][int(d[0])]) for d in designs
    ]


def _raw_model(specs, derive):
    by_case = {s.target_id: s.raw for s in specs}
    return lambda conditions, designs: [
        derive(None, list(by_case[conditions["case"]][int(d[0])])) for d in designs
    ]


def _attach(specs):
    document = _doc()
    return pps.attach_cells(
        T.rule(document, typed=(R32,)), document, T.PLAN, (tuple(specs),)
    )


@pytest.mark.parametrize("variant", [0, 1, 2])
def test_a_coded_row_grades_exactly_as_its_token(variant):
    specs = [
        _target("i0", False, T.IN_ROWS, variant),
        _target("e0", True, T.EDGE_ROWS, variant),
    ]
    assert any(
        type(v) is float and v < 0 for s in specs for row in s.raw for v in row
    )  # the codes are really in the rows
    attached = _attach(specs)
    tokens, coded = _token_model(specs), _raw_model(specs, tso.with_codes(_base_derive))
    check = pps.answer_check(attached)
    assert pool_grader.agen_predictions_valid(specs, coded, check) is True
    assert pool_grader.agen_predictions_valid(specs, tokens, check) is True
    assert pps.family_value(specs, coded, {}, T.PLAN, attached) == pps.family_value(
        specs, tokens, {}, T.PLAN, attached
    )
    assert pps.accuracy_record(specs, coded, T.PLAN, attached) == pps.accuracy_record(
        specs, tokens, T.PLAN, attached
    )
    for spec in specs:
        assert pps.target_cells(spec, coded, {}, T.PLAN, attached) == pps.target_cells(
            spec, tokens, {}, T.PLAN, attached
        )


def test_the_decode_must_run_before_the_validity_check():
    specs = [_target("i0", False, T.IN_ROWS, 0), _target("e0", True, T.EDGE_ROWS, 0)]
    attached = _attach(specs)
    check = pps.answer_check(attached)
    # the same rows WITHOUT the decode: a raw -1 is a negative time, an invalid answer
    assert (
        pool_grader.agen_predictions_valid(
            specs, _raw_model(specs, _base_derive), check
        )
        is False
    )


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_a_non_finite_typed_column_is_the_candidates_invalid_answer(bad):
    specs = [_target("i0", False, T.IN_ROWS, 0), _target("e0", True, T.EDGE_ROWS, 0)]
    rows = list(specs[1].raw)
    rows[0] = [rows[0][0], bad]
    specs[1] = SimpleNamespace(**{**vars(specs[1]), "raw": tuple(rows)})
    attached = _attach(specs)
    coded = _raw_model(specs, tso.with_codes(_base_derive))
    assert coded({"case": "e0"}, [[0.0]]) == [None]  # the derive refuses the row
    assert (
        pool_grader.agen_predictions_valid(specs, coded, pps.answer_check(attached))
        is False
    )


def test_decode_answer_touches_only_the_coded_columns():
    assert tso.decode_answer({"peak": -3.0, NAME: -0.93}) == {
        "peak": -3.0,
        NAME: "NEVER_REACHED",
    }
    assert tso.decode_answer({"peak": 1.0, "first_95c_crossing_s": -2.0}) == {
        "peak": 1.0,
        "first_95c_crossing_s": "NOT_REACHED",
    }
    assert tso.decode_answer({"peak": 1.0}) == {"peak": 1.0}
    assert tso.decode_answer({NAME: math.nan}) is None
    assert tso.decode_answer(None) is None
    answer = {NAME: -1.0}
    tso.decode_answer(answer)
    assert answer == {NAME: -1.0}  # a copy: the model's own answer is never edited

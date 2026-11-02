"""An A_gen slice answer the Challenge's validity gates refuse is a typed gate failure in the official grade (Validator 01:40).

Claims: an A_gen answer that passes the physics gates but derives to None (the Challenge's own validity gate refused it) gates the
submission as GATE_FAILED on the pool physics gate, names only that gate publicly, keeps its inner name private and gives no score,
where before agen_accuracy raised untyped (`agen_prediction_invalid`); the same refusal on a QUERYABLE answer is unchanged (the D side's
per-target prediction_invalid, no gate); a model whose every answer is valid grades exactly as before.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_pool_exam import (
    ARGUMENTS,
    CEILING,
    FAST,
    POLICIES,
    answers,
    exam_rows,
    grade,
    sets,
    toy_binding,
)
from test_pool_plugin import derive, fake_measure, good_serve

from carbon.scoring import pool_exam as exam
from carbon.scoring import pool_grader

MARK = 777.0  # a raw second output the toy derive refuses (passes the toy physics gate: only the first output is gated)


def _refusing_derive(row, raw):
    return None if raw[1] == MARK else derive(row, raw)


def _marking(index_of):
    """A serve that marks the answers at design `index_of(target)` of target t1 with MARK."""
    the_sets = sets()
    t1 = the_sets[0][0]
    marked = {tuple(t1.designs[i]) for i in index_of(t1)}

    def serve(rows):
        out = good_serve(rows)
        for i, row in enumerate(rows):
            if (row["x"], row["y"]) in marked:
                out[i] = [out[i][0], MARK]
        return out

    return serve, the_sets


def _measure(serve, the_sets):
    rows = exam_rows(the_sets)
    outputs = answers(rows, serve)
    return exam.measure_pool(
        binding=dataclasses.replace(toy_binding(), derive=_refusing_derive),
        sets=the_sets,
        policies=POLICIES,
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        base_measure=fake_measure,
        base_arguments=ARGUMENTS,
        speed_call_seconds=FAST,
        ceiling_seconds=CEILING,
    )


def test_an_a_gen_answer_the_validity_gates_refuse_is_a_typed_gate_failure():
    serve, the_sets = _marking(lambda t: [t.agen[0]])
    measured = _measure(serve, the_sets)
    assert measured["gates"][exam.PHYSICS_GATE] is False
    assert all(
        v is True for k, v in measured["gates"].items() if k != exam.PHYSICS_GATE
    )
    assert exam.AGEN_VALIDITY_GATE in measured["pool"]["physics_failed"]
    assert measured["D"] == 0.0
    assert exam.public(measured) == {
        "status": "GATE_FAILED",
        "gates": [exam.PHYSICS_GATE],
        "reasons": [],
    }


def test_before_the_gate_agen_accuracy_refused_it_untyped():
    serve, the_sets = _marking(lambda t: [t.agen[0]])
    specs = [s for group in the_sets for s in group]
    from carbon.scoring import pool_plugin

    predict = pool_plugin.pool_predictor(
        dataclasses.replace(toy_binding(), derive=_refusing_derive), serve
    )
    assert pool_grader.agen_predictions_valid(specs, predict) is False
    with pytest.raises(pool_grader.PoolRefused, match="agen_prediction_invalid"):
        pool_grader.agen_accuracy(specs, predict, POLICIES.agen_scales)


def test_the_same_refusal_on_a_queryable_answer_is_unchanged():
    serve, the_sets = _marking(
        lambda t: [i for i in range(len(t.designs)) if i not in set(t.agen)][:3]
    )
    measured = _measure(serve, the_sets)
    assert measured["gates"][exam.PHYSICS_GATE] is True
    assert exam.AGEN_VALIDITY_GATE not in measured["pool"].get("physics_failed", [])


def test_a_model_whose_answers_are_all_valid_grades_exactly_as_before():
    # the shared fixture's binding (no refusing derive) and the default serve: the existing grade, untouched
    assert grade() == grade()
    serve, the_sets = _marking(lambda t: [])
    plain = _measure(serve, the_sets)
    assert plain["gates"][exam.PHYSICS_GATE] is True
    assert plain == grade()

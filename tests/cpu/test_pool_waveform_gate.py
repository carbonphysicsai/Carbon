"""B6: the in-range accuracy gate grades a WAVEFORM output (Carbon Validator-Motor 11 Nov, MOT18_OC_GATE_AND_BUILDER_RULING
section 3: Motor 1.8's open-circuit back-EMF gate is enforced in the pack).

Claims:
- an in-range case's truth for an output registered as a waveform is its reference waveform with an absolute U > 0; a
  reference with no shape is the exam's typed reference fault (refused at attach, never a candidate failure);
- the case error is the registered waveform error / U (Motor: `back_emf.shape_error` / U), never |a - t| / u; the class's
  p90 is compared with the gate threshold of that output (pass / fail);
- an answer carrying the derive's other keys (Motor's torque scalars) is graded on the truth outputs only; an answer whose
  waveform has no shape is the grader's own invalid answer, so that class's gate fails;
- a case set with only scalar truths parses, validates and grades exactly as before.

Every waveform, case and value here is SYNTHETIC.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_pool_physics_score import attached, model, stand_set

from carbon.scoring import pool_grader
from carbon.scoring import pool_physics_score as pps

WAVE = "fixture_wave"
OC = "fixture:oc"


def _rms(values):
    return math.sqrt(sum(v * v for v in values) / len(values))


def _valid(value):
    try:
        values = [float(v) for v in value]
    except (TypeError, ValueError):
        return False
    return bool(values) and all(math.isfinite(v) for v in values) and _rms(values) > 0


def _error(predicted, true):
    # a synthetic shape error: the RMS of the difference over the RMS of the truth
    return _rms([p - t for p, t in zip(predicted, true, strict=True)]) / _rms(true)


@pytest.fixture
def waveform(monkeypatch):
    monkeypatch.setitem(
        pool_grader._WAVEFORMS,
        WAVE,
        pool_grader.WaveformOutput(valid=_valid, error=_error),
    )


TRUTH = [math.sin(2 * math.pi * k / 12) for k in range(12)]


def _document(truths, u=0.1, extra_case=None):
    cases = [
        {
            "class": OC,
            "inputs": {"cond": float(i)},
            "truths": {WAVE: list(t) if isinstance(t, list) else t},
            "u": {WAVE: u},
        }
        for i, t in enumerate(truths)
    ]
    if extra_case is not None:
        cases.append(extra_case)
    return {"schema": pps.IN_RANGE_CASES_SCHEMA, "cases": cases}


# ---------------------------------------------------------------- the case set


@pytest.mark.usefixtures("waveform")
def test_a_waveform_truth_parses_and_a_reference_with_no_shape_is_a_typed_reference_fault():
    cases = pps.in_range_cases(_document([TRUTH, TRUTH]))
    assert cases.cases[0][2] == {WAVE: tuple(TRUTH)}
    with pytest.raises(
        pps.PhysicsRefused, match="in_range_case_reference_has_no_shape"
    ):
        pps.in_range_cases(_document([TRUTH, [0.0] * 12]))
    for bad in ([], ["x"], [float("nan")] * 12, 3.0):
        with pytest.raises(pps.PhysicsRefused, match="in_range_case_malformed"):
            pps.in_range_cases(_document([bad]))
    # a scalar output never takes a list, and an output not registered as a waveform never does either
    for name in ("f", "fixture_not_registered"):
        case = {
            "class": OC,
            "inputs": {"cond": 9.0},
            "truths": {name: list(TRUTH)},
            "u": {name: 0.1},
        }
        with pytest.raises(pps.PhysicsRefused, match="in_range_case_malformed"):
            pps.in_range_cases(_document([TRUTH], extra_case=case))


def test_a_scalar_case_set_is_unchanged():
    document = {
        "schema": pps.IN_RANGE_CASES_SCHEMA,
        "cases": [
            {
                "class": OC,
                "inputs": {"cond": 1.0},
                "truths": {"f": 2, "g": 0.5},
                "u": {"f": 1.0, "g": 0.25},
            }
        ],
    }
    cases = pps.in_range_cases(document)
    truths = cases.cases[0][2]
    assert (
        truths == {"f": 2, "g": 0.5} and type(truths["f"]) is int
    )  # kept exactly as given
    # the answer check of a scalar case is the target one, extras and all
    for answer in (
        {"f": 1.0, "g": 1.0},
        {"f": 1.0, "g": 1.0, "h": 2.0},
        {"f": 1.0},
        {"f": float("nan"), "g": 1.0},
        None,
    ):
        assert pps._case_answer_valid(
            answer, {"f": 2, "g": 0.5}
        ) is pool_grader._valid_prediction(answer, ("f", "g"))


# ---------------------------------------------------------------- the error and the gate


def _gate(in_range, answers, threshold):
    specs, plan = stand_set()
    rule = attached(specs, plan, threshold={"f": 9.0, "g": 9.0, WAVE: threshold})
    rule = _replaced(rule, in_range)

    def case_predict(rows):
        assert [r["cond"] for r in rows] == [c[1]["cond"] for c in in_range.cases]
        return answers

    return pps.accuracy_record(specs, model(specs), plan, rule, case_predict)


def _replaced(rule, in_range):
    import dataclasses

    # the registered case set is exactly this one (its sha), as attach_cells would have checked
    return dataclasses.replace(
        rule, in_range=in_range, in_range_cases_sha256=in_range.sha256
    )


def _oc_row(record):
    (row,) = [r for r in record["rows"] if r["class"] == OC]
    return row


@pytest.mark.usefixtures("waveform")
def test_the_case_error_is_the_waveform_error_over_u_and_the_p90_gates():
    truths = [TRUTH] * 10
    in_range = pps.in_range_cases(_document(truths, u=0.1))
    # answers off by a growing scale: shape error = k x 0.05, so error / U = k x 0.5
    answers = [
        {WAVE: [(1 + 0.05 * k) * v for v in TRUTH], "mean_torque": 1.0, "ripple": 2.0}
        for k in range(10)
    ]
    expected = sorted(_error(a[WAVE], TRUTH) / 0.1 for a in answers)
    record = _gate(in_range, answers, threshold=10.0)
    row = _oc_row(record)
    assert (
        row["n"] == 10 and row["n_invalid"] == 0
    )  # the torque scalars did not make the answers invalid
    assert row["max"] == pytest.approx(expected[-1], rel=1e-12)
    assert (
        row["p90"] is not None and row["verdict"] == "PASS" and record["gate"]["passed"]
    )
    failing = _gate(in_range, answers, threshold=row["p90"] * 0.99)
    assert _oc_row(failing)["verdict"] == "FAIL" and failing["gate"]["passed"] is False


@pytest.mark.usefixtures("waveform")
def test_an_answer_with_no_shape_is_the_candidates_invalid_answer():
    in_range = pps.in_range_cases(_document([TRUTH] * 3))
    good = {WAVE: list(TRUTH)}
    for bad in ({WAVE: [0.0] * 12}, {}, {WAVE: "x"}, None):
        record = _gate(in_range, [good, good, bad], threshold=10.0)
        row = _oc_row(record)
        assert row["n_invalid"] == 1 and row["verdict"] == "FAIL", bad
        assert record["gate"]["passed"] is False


def test_motors_registered_waveform_error_is_shape_error():
    """With Motor 1.8's own registration, the case error is `back_emf.shape_error` / U."""
    from carbon.motor import back_emf
    from carbon.scoring import motor18_dual_pack

    output = motor18_dual_pack._waveform_output()
    name = "back_emf_open_circuit"
    previous = pool_grader._WAVEFORMS.get(name)
    pool_grader._WAVEFORMS[name] = output
    try:
        steps = back_emf.ANGLE_STEPS
        true = [
            math.sin(2 * math.pi * k / steps) + 0.2 * math.sin(6 * math.pi * k / steps)
            for k in range(steps)
        ]
        predicted = [1.1 * v + 0.01 for v in true]
        document = {
            "schema": pps.IN_RANGE_CASES_SCHEMA,
            "cases": [
                {
                    "class": OC,
                    "inputs": {"cond": 0.0},
                    "truths": {name: true},
                    "u": {name: 0.05},
                }
            ],
        }
        cases = pps.in_range_cases(document)
        ratios, invalid, outputs = {}, {}, {}
        pps._case_ratios(
            cases,
            lambda rows: [{name: predicted, "mean_torque_nm": 3.0}],
            ratios,
            invalid,
            outputs,
        )
        assert invalid == {}
        assert ratios[(OC, name)] == [
            back_emf.shape_error(predicted, tuple(true)) / 0.05
        ]
    finally:
        if previous is None:
            pool_grader._WAVEFORMS.pop(name, None)
        else:
            pool_grader._WAVEFORMS[name] = previous

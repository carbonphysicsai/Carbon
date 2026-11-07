"""Waveform outputs in the pool grade (TE-B 7 Nov, for Motor 1.8's k_e,ll cells): an additive path. With nothing
registered every check is the scalar one; a registered waveform output is graded by its own error, carries an absolute
U above zero, is never an objective or a limit, and may ride along on a target that does not grade it.

Synthetic toy values only (the toy problem of `test_pool_grader`), never production values.
"""

from __future__ import annotations

import math
import random

import pytest

from carbon.scoring import pool_grader, pool_physics_score
from carbon.scoring.pool_grader import Limit, PoolRefused, WaveformOutput, build_target

U = 0.01
WAVE = "w"


def _valid(value):
    return (
        type(value) in (list, tuple)
        and len(value) == 3
        and all(type(v) in (int, float) and math.isfinite(v) for v in value)
    )


def _error(predicted, true):
    return max(abs(p - t) for p, t in zip(predicted, true, strict=True))


OUTPUT = WaveformOutput(valid=_valid, error=_error)


@pytest.fixture
def registry():
    saved = dict(pool_grader._WAVEFORMS)
    pool_grader._WAVEFORMS.clear()
    yield pool_grader._WAVEFORMS
    pool_grader._WAVEFORMS.clear()
    pool_grader._WAVEFORMS.update(saved)


def _truth(x, y, wave=True):
    out = {"f": x + y, "g": x * x + y * y}
    if wave:
        out[WAVE] = [x, y, x - y]
    return out


def _target(outputs=("f", "g", WAVE), u=None, agen_count=8, **override):
    rng = random.Random(3)
    points = [(rng.random(), rng.random()) for _ in range(60)]
    points += [
        (0.63 + rng.uniform(-0.12, 0.12), 0.63 + rng.uniform(-0.12, 0.12))
        for _ in range(40)
    ]
    wave = WAVE in outputs
    arguments = {
        "target_id": "t0",
        "conditions": {"case": "t0"},
        "outputs": outputs,
        "objective": "f",
        "sense": "max",
        "limits": (Limit("g", "<=", 0.8),),
        "u": u or {k: U for k in outputs},
        "box": ((0.0, 1.0), (0.0, 1.0)),
        "designs": [list(p) for p in points],
        "truths": [_truth(*p, wave=wave) for p in points],
        "agen": range(len(points) - agen_count, len(points)),
        "start": (0.5, 0.5),
        "seed": 11,
    }
    return build_target(**{**arguments, **override})


# --- nothing registered: exactly the scalar checks ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prediction", "valid"),
    [
        ({"f": 1.0, "g": 2.0}, True),
        ({"f": 1.0}, False),
        ({"f": 1.0, "g": 2.0, "w": 3.0}, False),  # an extra key is invalid, as before
        ({"f": 1.0, "g": float("nan")}, False),
        ({"f": 1.0, "g": [1.0]}, False),
        ([1.0, 2.0], False),
        (None, False),
    ],
)
def test_with_nothing_registered_the_answer_check_is_the_scalar_one(
    registry, prediction, valid
):
    assert pool_grader._valid_prediction(prediction, ("f", "g")) is valid
    graded = pool_grader.graded_answer(prediction, ("f", "g"))
    assert graded is (prediction if valid else None)  # the same dict, never a copy


def test_with_nothing_registered_a_list_truth_refuses_the_pool(registry):
    with pytest.raises(PoolRefused, match="truth_must_give_every_output_finite"):
        _target()
    assert pool_grader.difference("f", 3.0, 1.5) == 1.5


# --- a registered waveform output ------------------------------------------------------------------------------------


def test_registration_is_add_only(registry):
    pool_grader.register_waveform_output(WAVE, OUTPUT)
    pool_grader.register_waveform_output(WAVE, OUTPUT)
    with pytest.raises(PoolRefused, match="already_registered_differently"):
        pool_grader.register_waveform_output(WAVE, WaveformOutput(_valid, abs))
    with pytest.raises(PoolRefused, match="registration_invalid"):
        pool_grader.register_waveform_output("", OUTPUT)


def test_a_waveform_target_keeps_its_truths_as_waveforms_and_round_trips(registry):
    pool_grader.register_waveform_output(WAVE, OUTPUT)
    spec = _target()
    assert all(type(t[WAVE]) is tuple and len(t[WAVE]) == 3 for t in spec.truths)
    again = pool_grader.load_pool(pool_grader.dump_pool(spec))
    assert again.digest == spec.digest and again.truths == spec.truths


@pytest.mark.parametrize(
    ("u", "code"),
    [
        ({"f": U, "g": U, WAVE: {"relative": 0.1}}, "absolute_u_above_zero"),
        ({"f": U, "g": U, WAVE: 0.0}, "absolute_u_above_zero"),
    ],
)
def test_a_waveform_output_needs_an_absolute_u_above_zero(registry, u, code):
    pool_grader.register_waveform_output(WAVE, OUTPUT)
    with pytest.raises(PoolRefused, match=code):
        _target(u=u)


def test_a_waveform_output_is_never_the_objective_or_a_limit(registry):
    pool_grader.register_waveform_output(WAVE, OUTPUT)
    with pytest.raises(PoolRefused, match="never_the_objective"):
        _target(objective=WAVE)
    with pytest.raises(PoolRefused, match="limits_must_name"):
        _target(limits=(Limit(WAVE, "<=", 1.0),))


def test_an_invalid_truth_waveform_refuses_the_pool(registry):
    pool_grader.register_waveform_output(WAVE, OUTPUT)
    with pytest.raises(PoolRefused, match="truth_must_give_every_output_finite"):
        _target(
            truths=[{"f": 0.1 * i, "g": 0.1, WAVE: [0.0, 1.0]} for i in range(100)]
        )


def test_the_answer_drops_registered_extras_and_checks_graded_waveforms(registry):
    pool_grader.register_waveform_output(WAVE, OUTPUT)
    answer = {"f": 1.0, "g": 2.0, WAVE: (0.0, 1.0, 2.0)}
    assert pool_grader.graded_answer(answer, ("f", "g")) == {"f": 1.0, "g": 2.0}
    assert pool_grader.graded_answer(answer, ("f", "g", WAVE)) is answer
    # an extra waveform that is not valid does not matter where it is not graded; where it is, the answer is invalid
    broken = {**answer, WAVE: (0.0, 1.0)}
    assert pool_grader.graded_answer(broken, ("f", "g")) == {"f": 1.0, "g": 2.0}
    assert pool_grader.graded_answer(broken, ("f", "g", WAVE)) is None
    # an extra key that is NOT a registered waveform output stays invalid
    assert pool_grader.graded_answer({**answer, "h": 1.0}, ("f", "g")) is None


def test_the_waveform_error_replaces_the_absolute_difference(registry):
    pool_grader.register_waveform_output(WAVE, OUTPUT)
    assert pool_grader.difference(WAVE, (1.0, 2.0, 3.0), (1.0, 2.5, 3.0)) == 0.5
    assert pool_grader.difference("f", 1.0, 3.0) == 2.0
    pool_grader._WAVEFORMS["bad"] = WaveformOutput(_valid, lambda p, t: -1.0)
    with pytest.raises(PoolRefused, match="waveform_error_invalid"):
        pool_grader.difference("bad", (0.0,), (0.0,))


def _offset_predict(spec, wave_shift):
    table = {tuple(d): t for d, t in zip(spec.designs, spec.truths, strict=True)}

    def predict(_conditions, designs):
        out = []
        for d in designs:
            truth = dict(table[tuple(d)])
            truth[WAVE] = tuple(v + wave_shift for v in truth[WAVE])
            out.append(truth)
        return out

    return predict


def test_agen_grades_the_waveform_by_its_error(registry):
    pool_grader.register_waveform_output(WAVE, OUTPUT)
    spec = _target()
    scales = {"f": 1.0, "g": 1.0, WAVE: 0.2}
    exact = pool_grader._target_agen(spec, _offset_predict(spec, 0.0), scales)
    shifted = pool_grader._target_agen(spec, _offset_predict(spec, 0.2), scales)
    assert exact == pytest.approx(1.0)
    # f and g exact (atom 1), the waveform off by 0.2 = 1 scale (atom 1 / 2): the mean of (1, 1, 1/2)
    assert shifted == pytest.approx((1.0 + 1.0 + 0.5) / 3)


def test_the_physics_ratios_grade_the_waveform_by_its_error(registry):
    pool_grader.register_waveform_output(WAVE, OUTPUT)
    spec = _target()
    rule = type("Rule", (), {"gate_cases": "agen"})()
    ratios, _raw, invalid = pool_physics_score._ratios(
        [(spec, "c")], _offset_predict(spec, 0.03), {"c": "out"}, rule
    )
    assert not invalid
    assert ratios[("c", WAVE)] == pytest.approx([0.03 / U] * len(spec.agen))
    assert ratios[("c", "f")] == pytest.approx([0.0] * len(spec.agen))


def test_a_scalar_target_grades_an_answer_carrying_a_waveform_it_does_not_grade(
    registry,
):
    pool_grader.register_waveform_output(WAVE, OUTPUT)
    spec = _target(outputs=("f", "g"))
    base = _offset_predict(_target(), 0.0)  # every answer carries the waveform too
    scales = {"f": 1.0, "g": 1.0}
    assert pool_grader.agen_predictions_valid([spec], base)
    assert pool_grader._target_agen(spec, base, scales) == pytest.approx(1.0)

"""F02 2.5's response leg anchors the on-time reference on the solver's local slope per probe group
(OWNER-MOTOR-SHEET-AND-F02-EXPONENT-01, owner "1 and a"): the registered global exponent held the solver's own
truth to A_response 0.85, so the solver's truth must score 1.0 while a model that is wrong in the slope still loses.
"""

from __future__ import annotations

import math
import random
import statistics

import pytest

from carbon.scoring import f02_physics, physics_half, pool_version, probe_design

# the registered F02 response spec (TRAIN-fitted global exponents; the on-time one is the defect)
SPEC = {
    "inputs": ["peak_w", "on_time_s"],
    "outputs": ["rise_c"],
    "exponent": [[1.169581, 0.084213]],
    "band": [[0.063318, 0.022745]],
    "span": [30.0, 2.0],
    "delta_range": [0.005, 0.015],
    "sign_gates": [
        {"input": "peak_w", "output": "rise_c", "sign": 1},
        {"input": "on_time_s", "output": "rise_c", "sign": 1},
    ],
}
TRAIN_STD = 6.701


def _truth(power, on_time):
    """A stand-in solver: rise ~ P^1.15 t^0.19 (local on-time sensitivity 0.19, not the registered 0.084)."""
    return 40.0 + 0.4 * power**1.15 * on_time**0.19


def _probe_rows(bases=((80.0, 4.5), (90.0, 5.2), (75.0, 5.7), (95.0, 4.2))):
    """Probe rows laid out as `probe_design`: per base the base, then +delta and -delta of each input."""
    rows = []
    for k, (power, on_time) in enumerate(bases):
        delta = (0.01 * 30.0, 0.01 * 2.0)
        point = [power, on_time]
        rows.append(_row(k, None, 0, point))
        for dim in (0, 1):
            for sign in (1, -1):
                moved = list(point)
                moved[dim] += sign * delta[dim]
                rows.append(_row(k, dim, sign, moved))
    return rows


def _row(k, dim, sign, point):
    return {
        "case_id": f"probe-{k}-{dim}-{sign}",
        "inputs": {"peak_w": point[0], "on_time_s": point[1]},
        "record": {"probe": {"base": k, "dim": dim, "sign": sign, "kind": "response"}},
    }


def _response(rows, peaks, definition=None):
    indexed = [(i, row["record"]["probe"]) for i, row in enumerate(rows)]
    inputs = [[row["inputs"]["peak_w"], row["inputs"]["on_time_s"]] for row in rows]
    override = f02_physics._group_reference(definition or {}, SPEC, indexed)
    return physics_half.response_benefit(
        probe_design.groups(indexed),
        lambda i: inputs[i],
        lambda i: [peaks[i] - 40.0],
        SPEC,
        [TRAIN_STD],
        override,
    )


def _peaks(rows):
    return [_truth(r["inputs"]["peak_w"], r["inputs"]["on_time_s"]) for r in rows]


def test_the_registered_global_exponent_holds_the_solvers_own_truth_below_one():
    rows = _probe_rows()
    score, record = _response(rows, _peaks(rows))
    assert score < 0.95 and record["mean_response_error"] > 0.05


def test_with_the_solvers_local_slope_per_group_the_solvers_own_truth_scores_one():
    rows = _probe_rows()
    peaks = _peaks(rows)
    slopes = f02_physics.local_slopes(rows, peaks, "on_time_s")
    assert set(slopes) == {"0", "1", "2", "3"}
    assert all(0.15 < v < 0.23 for v in slopes.values())  # about 0.19, not 0.084
    definition = {"group_response_reference": {"input": "on_time_s", "by_base": slopes}}
    score, record = _response(rows, peaks, definition)
    # power is inside its registered band already; on-time now sits on the solver's slope
    assert record["mean_response_error"] == 0.0 and score == 1.0
    assert record["sign_gate_failed"] == []


def test_a_model_with_the_wrong_slope_still_loses_against_the_solvers_reference():
    rows = _probe_rows()
    peaks = _peaks(rows)
    slopes = f02_physics.local_slopes(rows, peaks, "on_time_s")
    definition = {"group_response_reference": {"input": "on_time_s", "by_base": slopes}}
    flat = [
        40.0
        + 0.4 * r["inputs"]["peak_w"] ** 1.15 * 4.0**0.02  # barely moves with on-time
        for r in rows
    ]
    score, _ = _response(rows, flat, definition)
    assert score < 0.8


def test_the_reference_is_keyed_by_the_probe_base_not_by_position():
    rows = _probe_rows()
    peaks = _peaks(rows)
    slopes = f02_physics.local_slopes(rows, peaks, "on_time_s")
    shuffled = list(range(len(rows)))
    random.Random(4).shuffle(shuffled)
    # the same probes in a different bank order: same references, same score
    rows2 = [rows[i] for i in shuffled]
    peaks2 = [peaks[i] for i in shuffled]
    definition = {"group_response_reference": {"input": "on_time_s", "by_base": slopes}}
    assert _response(rows2, peaks2, definition)[0] == 1.0


def test_a_group_without_a_reference_is_a_refusal_never_the_registered_exponent():
    rows = _probe_rows()
    peaks = _peaks(rows)
    slopes = f02_physics.local_slopes(rows, peaks, "on_time_s")
    slopes.pop("2")
    definition = {"group_response_reference": {"input": "on_time_s", "by_base": slopes}}
    with pytest.raises(physics_half.PhysicsHalfRefused, match="reference_missing"):
        _response(rows, peaks, definition)


@pytest.mark.parametrize(
    "bad",
    [
        {"input": "nope", "by_base": {"0": 0.2}},
        {"input": "on_time_s", "by_base": {"0": "x"}},
        {"input": "on_time_s", "by_base": {0: 0.2}},
        {"input": "on_time_s"},
        [1, 2],
    ],
)
def test_a_malformed_group_reference_is_refused(bad):
    rows = _probe_rows()
    with pytest.raises(physics_half.PhysicsHalfRefused, match="malformed"):
        _response(rows, _peaks(rows), {"group_response_reference": bad})


def test_without_a_reference_nothing_changes_for_other_versions():
    rows = _probe_rows()
    peaks = _peaks(rows)
    assert _response(rows, peaks, {}) == _response(rows, peaks, None)
    indexed = [(i, r["record"]["probe"]) for i, r in enumerate(rows)]
    assert f02_physics._group_reference({}, SPEC, indexed) is None


def test_local_slopes_use_the_leg_formula_and_refuse_a_non_positive_rise():
    rows = _probe_rows()
    peaks = _peaks(rows)
    slopes = f02_physics.local_slopes(rows, peaks)
    base = 0
    plus, minus = 3, 4  # the +/- on-time pair of base 0 (rows: base, P+, P-, t+, t-)
    rise = peaks[base] - 40.0
    dx = (
        rows[plus]["inputs"]["on_time_s"] - rows[minus]["inputs"]["on_time_s"]
    ) / rows[base]["inputs"]["on_time_s"]
    assert slopes["0"] == pytest.approx(
        ((peaks[plus] - peaks[minus]) / rise) / dx, rel=1e-12
    )
    assert statistics.fmean(slopes.values()) == pytest.approx(0.19, abs=0.02)
    peaks[0] = 39.0
    with pytest.raises(physics_half.PhysicsHalfRefused):
        f02_physics.local_slopes(rows, peaks)


def test_the_pool_material_carries_a_valid_reference_or_none():
    base = {
        "schema": pool_version.MATERIAL_SCHEMA,
        "kind": "f02",
        "version": "2.5",
        "input_names": ["peak_w", "on_time_s"],
        "design_names": ["peak_w", "on_time_s"],
        "input_dtype": "<f4",
        "set_digest": "sha256:" + "0" * 64,
        "sets": [[{"x": 1}]],
    }
    assert pool_version.check_material(base) is base
    good = {
        **base,
        "response_reference": {"input": "on_time_s", "by_base": {"0": 0.19}},
    }
    assert pool_version.check_material(good) is good
    for bad in (
        {"input": "on_time_s", "by_base": {}},
        {"input": "on_time_s", "by_base": {"0": math.inf}},
        {"input": 3, "by_base": {"0": 0.19}},
        "slopes",
    ):
        with pytest.raises(Exception, match="pool_material_malformed"):
            pool_version.check_material({**base, "response_reference": bad})

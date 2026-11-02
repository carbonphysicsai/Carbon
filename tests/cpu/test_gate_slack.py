"""GATE-MARGIN-01, operator-side (scripts/dev/exam_reads/gate_slack.py): each per-answer physics gate's signed slack, read
beside the LIVE gate and checked against its verdict on every answer; the Validator's normalisation rulings; the pool's
near-limit design counts. The live gates and graders are not touched (nothing in carbon/ imports this module).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

READS = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "exam_reads"
sys.path.insert(0, str(READS))

import gate_slack

from carbon.motor import exam as motor_exam
from carbon.scoring import f02_physics, pool_adapters, pool_grader


def _laws(gates, raw, inputs=None):
    return gate_slack.answer_laws(gates, inputs or {}, raw)


# --- Motor: mean(torque) >= -allowance, m = slack / allowance --------------------------------------------------------


def test_motor_slack_is_the_mean_plus_its_own_allowance_and_matches_the_live_verdict():
    gates = pool_adapters.physics_gates("motor", "1.5")
    curve = [1.0] * 60
    law = _laws(gates, curve)["motoring_mean_nonnegative"]
    allowance = motor_exam.MEAN_ALLOWANCE_REL * 1.0 + motor_exam.MEAN_ALLOWANCE_FLOOR_NM
    assert law["slack"] == pytest.approx(1.0 + allowance)
    assert gate_slack.margin(law) == pytest.approx((1.0 + allowance) / allowance)
    # just inside and just outside the allowance: the live gate passes, then fails; the slack's sign follows
    edge = -(motor_exam.MEAN_ALLOWANCE_REL * 2.0 + motor_exam.MEAN_ALLOWANCE_FLOOR_NM)
    inside = [2.0] + [(edge * 60 - 2.0) / 59 + 1e-9] * 59
    outside = [2.0] + [(edge * 60 - 2.0) / 59 - 1e-6] * 59
    assert _laws(gates, inside)["motoring_mean_nonnegative"]["slack"] >= 0
    assert _laws(gates, outside)["motoring_mean_nonnegative"]["slack"] < 0
    assert "motoring_mean_nonnegative" in gates.failed({}, outside)


def test_a_malformed_answer_has_no_slack_and_its_schema_gate_fails():
    gates = pool_adapters.physics_gates("motor", "1.5")
    assert _laws(gates, [1.0] * 59) == {}
    assert "schema_finite" in gates.failed({}, [1.0] * 59)


# --- Cooling: two strict gates; a zero threshold has no registered scale ---------------------------------------------


@pytest.fixture
def cooling(monkeypatch):
    # the native (not encoded) answer space, for the live gate and the slack alike
    monkeypatch.setattr(pool_adapters, "_cooling_encoded", lambda version: False)
    return pool_adapters.physics_gates("cooling", "1.6")


def _cooling_row(peak=60.0, face=40.0, drop=500.0):
    return [peak] + [face] * 30 + [drop]


def test_cooling_slacks_follow_each_live_gate_including_the_strict_ones(cooling):
    inputs = {"inlet_c": 25.0}
    laws = _laws(cooling, _cooling_row(), inputs)
    assert laws["face_above_inlet"]["slack"] == pytest.approx(15.0)
    # an interval-scale comparison against the answer's own inputs: no registered scale, raw slack only
    assert gate_slack.margin(laws["face_above_inlet"]) is None
    assert laws["peak_bounds_profile"]["slack"] > 0
    assert laws["pressure_drop_positive"]["slack"] == 500.0
    assert gate_slack.margin(laws["pressure_drop_positive"]) is None
    assert all(law["scale"] is None for law in laws.values())
    # strict: a face exactly at the inlet and a zero pressure drop FAIL with a slack of exactly 0
    at_inlet = _laws(cooling, _cooling_row(face=25.0), inputs)["face_above_inlet"]
    assert at_inlet["slack"] == 0 and not gate_slack.passes(at_inlet)
    assert "face_above_inlet" in cooling.failed(inputs, _cooling_row(face=25.0))
    zero = _laws(cooling, _cooling_row(drop=0.0), inputs)["pressure_drop_positive"]
    assert zero["slack"] == 0 and not gate_slack.passes(zero)
    # a peak below the profile's max (beyond the float32 allowance) fails
    low = _laws(cooling, _cooling_row(peak=39.0), inputs)["peak_bounds_profile"]
    assert low["slack"] < 0 and "peak_bounds_profile" in cooling.failed(
        inputs, _cooling_row(peak=39.0)
    )


# --- F02: peak >= INITIAL_C ------------------------------------------------------------------------------------------


def test_f02_slack_is_the_peak_above_the_initial_temperature():
    gates = pool_adapters.physics_gates("f02", "2.5")
    at = _laws(gates, [f02_physics.INITIAL_C])["peak_not_below_initial"]
    assert at["slack"] == 0 and gate_slack.passes(at)
    below = _laws(gates, [f02_physics.INITIAL_C - 0.5])["peak_not_below_initial"]
    assert below["slack"] == pytest.approx(-0.5) and gate_slack.margin(below) is None
    assert "peak_not_below_initial" in gates.failed({}, [f02_physics.INITIAL_C - 0.5])


# --- F08: the laws on the named summary (the native-summary check is the live one, stubbed alike) --------------------


def test_f08_slacks_are_the_tightest_peak_and_ordering_gaps(monkeypatch):
    from carbon.scoring import f08_dual_measurement, f08_dual_pack

    names = (
        "static_tip_mm_per_n",
        "peak_tip_z005_mm_per_n",
        "peak_tip_z010_mm_per_n",
        "peak_tip_z020_mm_per_n",
    )
    monkeypatch.setattr(f08_dual_pack, "_targets", lambda version: names)
    monkeypatch.setattr(f08_dual_measurement, "native_summary", lambda row, **k: True)
    gates = pool_adapters.physics_gates("f08", "1.6")
    laws = _laws(gates, [0.10, 0.40, 0.30, 0.25])
    assert laws["peak_not_below_static"]["slack"] == pytest.approx(0.15)
    assert laws["peaks_ordered_by_damping"]["slack"] == pytest.approx(0.05)
    assert (
        gate_slack.margin(laws["peaks_ordered_by_damping"]) is None
    )  # no registered scale
    bad = _laws(gates, [0.10, 0.20, 0.30, 0.25])["peaks_ordered_by_damping"]
    assert bad["slack"] < 0 and "peaks_ordered_by_damping" in gates.failed(
        {}, [0.10, 0.20, 0.30, 0.25]
    )


# --- the parity STOP --------------------------------------------------------------------------------------------------


def test_a_slack_that_disagrees_with_the_live_verdict_stops():
    real = pool_adapters.physics_gates("motor", "1.5")
    lying = SimpleNamespace(
        kind="motor",
        version="1.5",
        gate_names=real.gate_names,
        failed=lambda inputs, raw: (
            "motoring_mean_nonnegative",
        ),  # says fail on a clear pass
    )
    with pytest.raises(gate_slack.SlackParity, match="motoring_mean_nonnegative"):
        _laws(lying, [1.0] * 60)
    passes_malformed = SimpleNamespace(
        kind="motor", version="1.5", gate_names=real.gate_names, failed=lambda i, r: ()
    )
    with pytest.raises(gate_slack.SlackParity, match="schema_finite"):
        _laws(passes_malformed, [1.0] * 59)


# --- the entry summary and physics_pool's m ---------------------------------------------------------------------------


def test_physics_pool_m_is_the_minimum_over_the_entrys_answers_with_band_counts():
    gates = pool_adapters.physics_gates("motor", "1.5")
    # a flat curve at -0.95 a, where a is its own allowance (REL x |curve| + FLOOR): m = 0.05, near-gate
    allowance = motor_exam.MEAN_ALLOWANCE_FLOOR_NM / (
        1 - 0.95 * motor_exam.MEAN_ALLOWANCE_REL
    )
    near = -0.95 * allowance
    raw_rows = [[1.0] * 60, [near] * 60, [1.0] * 59]
    rows = [{"inputs": {}} for _ in raw_rows]
    summary = gate_slack.entry_summary(gates, rows, raw_rows)
    law = summary["laws"]["motoring_mean_nonnegative"]
    assert summary["schema_failed"] == 1
    assert law["answers"] == 2 and law["near"] == 1 and law["fail"] == 0
    assert law["m_min"] == pytest.approx(0.05, rel=1e-6)
    # a schema failure leaves physics_pool with no margin (it failed on a gate with none)
    assert gate_slack.physics_pool_m(summary) is None
    clean = gate_slack.entry_summary(gates, rows[:2], raw_rows[:2])
    assert gate_slack.physics_pool_m(clean) == pytest.approx(0.05, rel=1e-6)


def test_a_law_with_no_registered_scale_leaves_physics_pool_without_m(cooling):
    rows = [{"inputs": {"inlet_c": 25.0}}]
    summary = gate_slack.entry_summary(cooling, rows, [_cooling_row()])
    assert summary["laws"]["pressure_drop_positive"]["unscaled"] == 1
    assert summary["laws"]["pressure_drop_positive"]["m_min"] is None
    assert summary["laws"]["face_above_inlet"]["m_min"] is None
    assert summary["laws"]["face_above_inlet"]["slack_min"] == pytest.approx(15.0)
    assert gate_slack.physics_pool_m(summary) is None


# --- near-limit design counts ----------------------------------------------------------------------------------------


def test_near_limit_counts_use_the_pools_own_margins_and_u_per_limit_and_class():
    ripple = pool_grader.Limit("ripple", "<=", 0.30)
    hydraulic = pool_grader.Limit("hydraulic_w", "<=", 0.25)

    def spec(truths, shell, excluded):
        return SimpleNamespace(
            limits=(ripple, hydraulic),
            truths=tuple(truths),
            u_at=lambda index, name, t=tuple(truths): pool_grader.u_value(
                {"ripple": 0.026, "hydraulic_w": {"relative": 0.03}}[name],
                t[index][name],
            ),
            excluded=excluded,
            shell=shell,
        )

    inner = spec(
        [
            {
                "ripple": 0.25,
                "hydraulic_w": 0.10,
            },  # ripple 0.05 away: beyond 1U, within 3U (0.078)
            {
                "ripple": 0.40,
                "hydraulic_w": 0.26,
            },  # ripple 0.10 away; hydraulic 0.01 (U 0.0078, 3U 0.0234)
        ],
        None,
        2,
    )
    outer = spec([{"ripple": 0.31, "hydraulic_w": 0.50}], {"mode": "designs"}, 1)
    counts = gate_slack.near_limit_counts(
        [inner, outer], lambda s: "extended_shell" if s.shell else "in_train"
    )
    r = counts["limits"]["ripple <= 0.3"]
    assert r["in_train"] == {"designs": 2, "within_u": 0, "within_3u": 1}
    assert r["extended_shell"] == {"designs": 1, "within_u": 1, "within_3u": 1}
    assert r["total"] == {"designs": 3, "within_u": 1, "within_3u": 2}
    h = counts["limits"]["hydraulic_w <= 0.25"]["in_train"]
    assert h == {
        "designs": 2,
        "within_u": 0,
        "within_3u": 1,
    }  # relative U is 0.03 x the true value
    assert counts["excluded_at_build"] == {"in_train": 2, "extended_shell": 1}


def test_no_grader_imports_the_slack_reader():
    root = Path(__file__).resolve().parents[2] / "carbon"
    users = [
        p for p in root.rglob("*.py") if "gate_slack" in p.read_text(encoding="utf-8")
    ]
    assert users == []
    assert math.isclose(gate_slack.NEAR, 0.10)

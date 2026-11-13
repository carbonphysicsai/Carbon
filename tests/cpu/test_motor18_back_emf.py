"""Motor 1.8 k_e,ll and its shape error (`carbon.motor.back_emf`), as the Validator defined them (6 Nov 05:23 / 05:25).

Synthetic linkage waveforms only (never solver values): the derivative stencil is exact on quadratics, k_e matches an
analytic derivative, the shape error removes amplitude and keeps sign, and every unscorable input is typed.
"""

from __future__ import annotations

import math

import pytest

from carbon.motor import back_emf
from carbon.motor.domain import ANGLE_STEPS, FIXED

H = back_emf.STEP_RAD
THETA = [k * H for k in range(ANGLE_STEPS)]
POLE_PAIRS = FIXED["poles"] // 2


def _balanced(amplitude=0.02, shift=0.3):
    """A synthetic balanced three-phase linkage set (electrical angle = pole pairs x mechanical)."""
    return {
        phase: [
            amplitude * math.cos(POLE_PAIRS * t + shift - k * 2 * math.pi / 3)
            for t in THETA
        ]
        for k, phase in enumerate(back_emf.PHASES)
    }


def test_the_step_is_a_quarter_degree_in_mechanical_radians():
    assert back_emf.STEP_RAD == pytest.approx(math.radians(0.25))
    assert len(THETA) == ANGLE_STEPS == 60


def test_the_stencil_is_exact_on_a_quadratic_at_the_ends_too():
    values = [3.0 + 2.0 * t - 5.0 * t * t for t in THETA]
    exact = [2.0 - 10.0 * t for t in THETA]
    got = back_emf.derivative(values)
    assert got == pytest.approx(exact, rel=1e-9, abs=1e-9)


def test_the_window_is_never_wrapped():
    """A ramp is not periodic: a wrapped stencil would put a huge spike at the ends; this one stays flat."""
    got = back_emf.derivative([7.0 * t for t in THETA])
    assert got == pytest.approx([7.0] * ANGLE_STEPS, rel=1e-9)


def test_ke_line_is_the_derivative_of_a_minus_b_with_increasing_angle():
    lam = _balanced()
    got = back_emf.ke_line(lam)
    exact = [
        -0.02
        * POLE_PAIRS
        * (
            math.sin(POLE_PAIRS * t + 0.3)
            - math.sin(POLE_PAIRS * t + 0.3 - 2 * math.pi / 3)
        )
        for t in THETA
    ]
    assert got == pytest.approx(exact, rel=2e-3, abs=1e-6)


def test_the_shape_error_removes_amplitude_and_keeps_sign():
    lam = _balanced()
    true = back_emf.ke_line(lam)
    assert back_emf.shape_error([7.0 * v for v in true], true) == pytest.approx(
        0.0, abs=1e-12
    )
    assert back_emf.shape_error([-v for v in true], true) == pytest.approx(
        2.0, rel=1e-9
    )
    scaled = {p: [3.0 * v for v in w] for p, w in lam.items()}
    assert back_emf.grade(scaled, lam) == pytest.approx(0.0, abs=1e-12)


def test_a_different_shape_scores_a_positive_error():
    lam = _balanced()
    other = _balanced(shift=0.9)
    error = back_emf.grade(other, lam)
    assert 0.0 < error < 2.0


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {"a": [0.0] * ANGLE_STEPS, "b": [0.0] * ANGLE_STEPS},
        {"a": [0.0] * 59, "b": [0.0] * ANGLE_STEPS, "c": [0.0] * ANGLE_STEPS},
        {
            "a": [math.nan] * ANGLE_STEPS,
            "b": [0.0] * ANGLE_STEPS,
            "c": [0.0] * ANGLE_STEPS,
        },
        {"a": ["x"] * ANGLE_STEPS, "b": [0.0] * ANGLE_STEPS, "c": [0.0] * ANGLE_STEPS},
        {"a": [True] * ANGLE_STEPS, "b": [0.0] * ANGLE_STEPS, "c": [0.0] * ANGLE_STEPS},
    ],
)
def test_a_malformed_prediction_is_typed_never_scored(bad):
    with pytest.raises(back_emf.BackEmfUnavailable) as refused:
        back_emf.grade(bad, _balanced())
    assert refused.value.code == "prediction_flux_linkage_invalid"


def test_a_shapeless_waveform_is_typed_on_its_own_side():
    lam = _balanced()
    flat = {
        p: [0.01] * ANGLE_STEPS for p in back_emf.PHASES
    }  # constant linkage: k_e is zero
    with pytest.raises(
        back_emf.BackEmfUnavailable, match="reference_waveform_has_no_shape"
    ):
        back_emf.grade(lam, flat)
    with pytest.raises(
        back_emf.BackEmfUnavailable, match="prediction_waveform_has_no_shape"
    ):
        back_emf.grade(flat, lam)


def test_the_consistency_record_covers_bc_and_ca_only():
    record = back_emf.consistency(_balanced())
    assert set(record) == {"bc", "ca"}
    assert all(math.isfinite(v) and v >= 0 for v in record.values())


def test_no_cell_scores_before_its_own_u_is_registered():
    for cell in back_emf.CELLS:
        for registered in (
            None,
            {},
            {cell: None},
            {cell: 0.0},
            {cell: math.inf},
            {cell: "1"},
            {cell: True},
        ):
            with pytest.raises(
                back_emf.BackEmfUnavailable, match="u_not_registered_" + cell
            ):
                back_emf.require_u(registered, cell)
        assert back_emf.require_u({cell: 0.07}, cell) == 0.07
    with pytest.raises(back_emf.BackEmfUnavailable, match="cell_unregistered"):
        back_emf.require_u({"back_emf": 1.0}, "back_emf")

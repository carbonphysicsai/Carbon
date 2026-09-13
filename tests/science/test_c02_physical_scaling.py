"""Independent manufactured-solution checks for C-02 Burgers operations."""

from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from carbon.reconstruction._vendor.carbon_jax_lab.training import (
    burgers_residual,
    conservative_advection,
    spectral_derivative,
    temporal_derivative,
)
from carbon.reconstruction.scaling import BurgersPhysicalScaling

LENGTH = 2.75
TIME = 0.8
VELOCITY = 1.6
VISCOSITY = 0.037


def _manufactured(x: object, t: object):
    theta = 2 * jnp.pi * x / LENGTH
    tau = t / TIME
    return VELOCITY * (
        0.3
        + 0.2 * jnp.cos(theta) * jnp.sin(1.3 * tau)
        - 0.15 * jnp.sin(2 * theta) * jnp.cos(0.7 * tau)
    )


def _analytic(x: object, t: object):
    theta = 2 * np.pi * np.asarray(x) / LENGTH
    tau = float(t) / TIME
    u = VELOCITY * (
        0.3
        + 0.2 * np.cos(theta) * np.sin(1.3 * tau)
        - 0.15 * np.sin(2 * theta) * np.cos(0.7 * tau)
    )
    ut = (VELOCITY / TIME) * (
        0.2 * 1.3 * np.cos(theta) * np.cos(1.3 * tau)
        + 0.15 * 0.7 * np.sin(2 * theta) * np.sin(0.7 * tau)
    )
    ux = (VELOCITY / LENGTH) * (
        -0.2 * 2 * np.pi * np.sin(theta) * np.sin(1.3 * tau)
        - 0.15 * 4 * np.pi * np.cos(2 * theta) * np.cos(0.7 * tau)
    )
    uxx = (VELOCITY / LENGTH**2) * (
        -0.2 * (2 * np.pi) ** 2 * np.cos(theta) * np.sin(1.3 * tau)
        + 0.15 * (4 * np.pi) ** 2 * np.sin(2 * theta) * np.cos(0.7 * tau)
    )
    return u, ut, ux, uxx


def test_physical_scaling_is_explicit_reversible_and_casewise() -> None:
    scaling = BurgersPhysicalScaling(
        LENGTH, TIME, VELOCITY, "carbon_burgers_si_example_v1"
    )
    x = np.array([0.0, 0.31, LENGTH - 0.1], dtype=np.float64)
    t = np.array([0.03, 0.4], dtype=np.float64)
    u = np.array([-2.1, 0.4, 3.2], dtype=np.float64)
    nu = np.array([0.01, 0.07], dtype=np.float64)

    np.testing.assert_array_equal(
        scaling.to_physical_position(scaling.to_dimensionless_position(x)), x
    )
    np.testing.assert_array_equal(
        scaling.to_physical_time(scaling.to_dimensionless_time(t)), t
    )
    np.testing.assert_array_equal(
        scaling.to_physical_velocity(scaling.to_dimensionless_velocity(u)), u
    )
    np.testing.assert_allclose(scaling.viscosity_coefficient(nu), nu * TIME / LENGTH**2)
    assert scaling.advection_coefficient == VELOCITY * TIME / LENGTH
    scaling.assert_representable("float32")
    with pytest.raises(ValueError, match="incompatible"):
        scaling.require_unit_system("guessed_units")
    with pytest.raises(ValueError, match="positive"):
        scaling.viscosity_coefficient(np.array([0.0]))


def test_manufactured_forcing_residual_and_periodic_identities() -> None:
    errors: list[tuple[float, float]] = []
    with jax.enable_x64():
        t = jnp.asarray(0.43, dtype=jnp.float64)
        for points in (12, 18, 36):
            x = jnp.arange(points, dtype=jnp.float64) * LENGTH / points
            u_expected, ut_expected, ux_expected, uxx_expected = _analytic(x, t)
            u = _manufactured(x, t)
            ut = temporal_derivative(
                lambda value, grid=x: _manufactured(grid, value), t
            )
            ux = spectral_derivative(u, LENGTH, 1)
            uxx = spectral_derivative(u, LENGTH, 2)
            forcing = ut_expected + u_expected * ux_expected - VISCOSITY * uxx_expected
            forced_residual = (
                burgers_residual(u, ut, jnp.asarray(VISCOSITY), LENGTH) - forcing
            )
            rms = float(jnp.sqrt(jnp.mean(forced_residual**2)))
            maximum = float(jnp.max(jnp.abs(forced_residual)))
            errors.append((rms, maximum))

            np.testing.assert_allclose(ut, ut_expected, rtol=2e-13, atol=2e-13)
            np.testing.assert_allclose(ux, ux_expected, rtol=2e-13, atol=2e-13)
            np.testing.assert_allclose(uxx, uxx_expected, rtol=2e-12, atol=2e-12)
            assert abs(float(jnp.mean(ux))) < 2e-14
            assert abs(float(jnp.mean(conservative_advection(u, LENGTH)))) < 2e-14

    # Twelve points truncates the nonlinear fourth harmonic at the strict
    # two-thirds cutoff. Eighteen points resolves it, after which roundoff is
    # the dominant floor rather than an invented scientific threshold.
    assert errors[1][0] < errors[0][0] * 1e-10
    assert errors[1][1] < errors[0][1] * 1e-10
    assert errors[1][0] < 2e-13
    assert errors[1][1] < 6e-13
    assert errors[2][0] < 5e-13
    assert errors[2][1] < 2e-12


def test_dimensionless_coefficients_reconstruct_the_physical_residual() -> None:
    scaling = BurgersPhysicalScaling(
        LENGTH, TIME, VELOCITY, "carbon_burgers_si_example_v1"
    )
    with jax.enable_x64():
        points = 36
        x = jnp.arange(points, dtype=jnp.float64) * LENGTH / points
        t = jnp.asarray(0.29, dtype=jnp.float64)
        u, ut, _ux, _uxx = _analytic(x, t)
        physical = burgers_residual(
            jnp.asarray(u), jnp.asarray(ut), jnp.asarray(VISCOSITY), LENGTH
        )
        u_hat = jnp.asarray(u) / VELOCITY
        ut_hat = jnp.asarray(ut) * TIME / VELOCITY
        dimensionless = (
            ut_hat
            + scaling.advection_coefficient * conservative_advection(u_hat, 1.0)
            - scaling.viscosity_coefficient(np.array(VISCOSITY)).item()
            * spectral_derivative(u_hat, 1.0, 2)
        )
        physical_array = np.asarray(physical)
        reconstructed_array = np.asarray((VELOCITY / TIME) * dimensionless)

    np.testing.assert_allclose(
        physical_array, reconstructed_array, rtol=2e-12, atol=2e-12
    )

"""Frozen analytic verification controls; no model inference or training."""

from __future__ import annotations
import math
import numpy as np
from .development import crossing, measure

RECIPES = {
    "calibration": {
        "nu": 0.2,
        "a": 0.25,
        "mode": 1,
        "mean": 0.0,
        "horizon": 2.0,
        "points": 64,
        "times": 65,
    },
    "verification-v1": {
        "nu": 0.13,
        "a": 0.35,
        "mode": 2,
        "mean": 0.1,
        "horizon": 1.5,
        "points": 128,
        "times": 129,
    },
}

RECIPES["verification-v2"] = {
    "nu": 0.17,
    "a": 0.42,
    "mode": 3,
    "mean": -0.07,
    "horizon": 1.2,
    "points": 256,
    "times": 193,
}


def controls(stage):
    p = RECIPES[stage]
    t = np.linspace(0, p["horizon"], p["times"])
    x = np.arange(p["points"]) * 2 * np.pi / p["points"]
    nu, a, k, mean = p["nu"], p["a"], p["mode"], p["mean"]

    def exact(times, phase=0.0):
        b = a * np.exp(-nu * k * k * times[:, None])
        theta = k * (x[None, :] - mean * times[:, None]) + phase
        return mean + 2 * nu * k * b * np.sin(theta) / (1 + b * np.cos(theta))

    ref = exact(t)
    initial = ref[0]
    amplitude = float(max(abs(initial - mean)))

    def run(u, ts=t, reference=ref):
        return measure(
            u,
            reference,
            times=ts,
            length=2 * math.pi,
            viscosity=nu,
            initial=initial,
            amplitude=amplitude,
            characteristic_time=1 / (amplitude * k),
        )

    ramp = (t / t[-1])[:, None]
    phase = exact(t, 0.15)
    phase[0] = initial
    wrong = exact(t * 0.5)
    wrong[0] = initial
    fast = exact(t * 1.5)
    fast[0] = initial
    localized = ref + 0.08 * amplitude * ramp * np.exp(
        -(((x - math.pi) / (2 * math.pi / 20)) ** 2)
    )
    overshoot = ref.copy()
    overshoot[1:] = mean + 2 * (initial - mean)
    frozen = np.broadcast_to(initial, ref.shape).copy()
    suppressed = mean + (ref - mean) * np.exp(-8 * ramp)
    suppressed[0] = initial
    shifted = exact(t, 2 * np.pi / p["points"] * k)
    shifted[0] = initial
    cases = {
        "exact": ref,
        "mean_drift": ref + 0.02 * amplitude * ramp,
        "excessive_amplitude": overshoot,
        "wrong_decay": wrong,
        "fast_decay": fast,
        "temporal_phase": phase,
        "localized_error": localized,
        "plausible_statistics_wrong_trajectory": shifted,
        "frozen_initial": frozen,
        "suppressed_dynamics": suppressed,
    }
    results = {name: run(u) for name, u in cases.items()}
    # Independent closed-form spatial derivative, not the FFT implementation.
    b = a * np.exp(-nu * k * k * t[:, None])
    theta = k * (x[None, :] - mean * t[:, None])
    ux = 2 * nu * k * k * b * (np.cos(theta) + b) / (1 + b * np.cos(theta)) ** 2
    # u_t = -mean*u_x - 2*nu^2*k^3*b*sin(theta)/(1+b*cos(theta))^2.
    ut = (
        -mean * ux
        - 2 * nu * nu * k**3 * b * np.sin(theta) / (1 + b * np.cos(theta)) ** 2
    )
    edot = 2 * np.pi * np.mean((ref - mean) * ut, axis=1)
    diss = nu * 2 * np.pi * np.mean(ux * ux, axis=1)
    identity_error = float(np.max(np.abs(edot + diss)))
    # Cross-time energy quadrature convergence against the analytic identity.
    coarse = run(exact(t[::2]), t[::2], exact(t[::2]))
    fine = results["exact"]
    checks = {
        "reference_agreement": fine["metrics"]["field_time_rms"] == 0
        and fine["metrics"]["energy_path_rms"] == 0,
        "analytic_energy_identity": identity_error < 1e-12,
        "analytic_mean": float(np.max(abs(ref.mean(axis=1) - mean))) < 1e-12,
        "balance_refines": fine["metrics"]["integrated_energy_balance"]
        < coarse["metrics"]["integrated_energy_balance"] / 3,
        "mean_drift_detected": results["mean_drift"]["metrics"]["conserved_mean"]
        > 0.019,
        "excessive_amplitude_detected": results["excessive_amplitude"]["metrics"][
            "maximum_principle"
        ]
        > 0.9,
        "wrong_decay_despite_monotonicity": results["wrong_decay"]["diagnostics"][
            "positive_sampled_energy_increment"
        ]
        < 1e-12
        and results["wrong_decay"]["metrics"]["integrated_energy_balance"] > 0.05,
        "phase_detected": results["temporal_phase"]["metrics"]["field_time_rms"] > 0.02,
        "localized_detected": results["localized_error"]["metrics"]["field_time_rms"]
        > 0.005,
        "aggregate_blind_spot_exposed": results[
            "plausible_statistics_wrong_trajectory"
        ]["metrics"]["field_time_rms"]
        > 0.01
        and results["plausible_statistics_wrong_trajectory"]["metrics"][
            "energy_path_rms"
        ]
        < 1e-12,
        "frozen_initial_rejected": results["frozen_initial"]["metrics"][
            "integrated_energy_balance"
        ]
        > 0.05,
        "suppressed_dynamics_detected": results["suppressed_dynamics"]["metrics"][
            "energy_path_rms"
        ]
        > 0.1,
        "absent_crossing_explicit": crossing([1.0, 1.0, 1.0], [0.0, 1.0, 2.0], 0.5)
        == {"status": "RIGHT_CENSORED", "time": None},
        "crossing_interpolates": crossing([1.0, 0.75, 0.25], [0.0, 1.0, 2.0], 0.5)
        == {"status": "OBSERVED", "time": 1.5},
        "left_censor_explicit": crossing([0.1, 0.1, 0.1], [0.0, 1.0, 2.0], 0.5)[
            "status"
        ]
        == "LEFT_CENSORED",
        "representation_no_credit": all(
            v["diagnostics"]["periodic_closure"]
            == "ENFORCED_BY_REPRESENTATION_NO_QUALITY_CREDIT"
            for v in results.values()
        ),
    }
    # Nonuniform times: constant spatial offset with known time-linear amplitude.
    nt = t[-1] * np.linspace(0, 1, 513) ** 2
    nref = exact(nt)
    perturb = nref + amplitude * (nt / nt[-1])[:, None]
    observed = run(perturb, nt, nref)["metrics"]["field_time_rms"]
    expected = amplitude / (
        math.sqrt(3) * float(np.sqrt(np.mean((initial - mean) ** 2)))
    )
    checks["wrong_decay_energy_envelope"] = (
        results["wrong_decay"]["metrics"]["energy_path_max"] > 0.05
    )
    checks["frozen_initial_energy_envelope"] = (
        results["frozen_initial"]["metrics"]["energy_path_max"] > 0.05
    )
    checks["suppressed_energy_envelope"] = (
        results["suppressed_dynamics"]["metrics"]["energy_path_max"] > 0.05
    )
    checks["exact_energy_envelope"] = (
        results["exact"]["metrics"]["energy_path_max"] == 0
    )
    checks["nonuniform_time_weights"] = abs(observed / expected - 1) < 1e-5
    return {
        "schema": "carbon.cw1.measurement-controls.v1",
        "stage": stage,
        "recipe": p,
        "provenance": "ANALYTIC_SYNTHETIC_CONTROL_NOT_REAL_MODEL",
        "checks": checks,
        "passed": all(checks.values()),
        "results": results,
        "independent_energy_identity_max_absolute": identity_error,
        "coarse_balance": coarse["metrics"]["integrated_energy_balance"],
        "nonuniform_relative_error": abs(observed / expected - 1),
    }

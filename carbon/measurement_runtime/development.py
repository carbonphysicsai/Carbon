"""Versioned derived DEVELOPMENT measurements; historical C-05 is unchanged.

Operators consume validated arrays inside the evaluator. No result is itself an
acceptance, qualified uncertainty bound, official ScoreInput or public payload.
"""

from __future__ import annotations

import math

import numpy as np

VERSION = "carbon.c05.burgers-development-derived.v3"
METRICS = (
    "field_time_rms",
    "energy_path_rms",
    "initial_condition",
    "conserved_mean",
    "maximum_principle",
    "integrated_energy_balance",
    "energy_path_max",
)


def time_average(values, times):
    values, times = np.asarray(values), np.asarray(times)
    return np.sum((values[:-1] + values[1:]) * np.diff(times) / 2) / (
        times[-1] - times[0]
    )


def crossing(energy, times, target):
    # Absence is an interval observation, never the numerical endpoint.
    if energy[0] <= target:
        return {"status": "LEFT_CENSORED", "time": None}
    for j in range(1, len(times)):
        if energy[j] <= target < energy[j - 1]:
            t = times[j - 1] + (times[j] - times[j - 1]) * (energy[j - 1] - target) / (
                energy[j - 1] - energy[j]
            )
            return {"status": "OBSERVED", "time": float(t)}
    return {"status": "RIGHT_CENSORED", "time": None}


def measure(
    values,
    reference,
    *,
    times,
    length,
    viscosity,
    initial,
    amplitude,
    characteristic_time,
):
    """Rectangular periodic binary64 samples; trapezoid time, equal-space quadrature.

    The caller owns exact artifact association. This numeric function confers no
    provenance. Units: field U; energy L U^2; dissipation L U^2/T; balance L U^2.
    """
    u, v, t, u0 = (
        np.asarray(x, dtype=np.float64) for x in (values, reference, times, initial)
    )
    if (
        u.ndim != 2
        or u.shape != v.shape
        or u.shape[1] != len(u0)
        or not 3 <= len(t) == u.shape[0] <= 1025
        or not 32 <= u.shape[1] <= 4096
        or t[0] != 0
        or np.any(np.diff(t) <= 0)
        or any(not np.all(np.isfinite(x)) for x in (u, v, t, u0))
        or any(
            not math.isfinite(x) or x <= 0
            for x in (length, viscosity, amplitude, characteristic_time)
        )
    ):
        raise ValueError("finite complete periodic field and physical scales required")
    a0 = float(np.sqrt(np.mean((u0 - u0.mean()) ** 2)))
    if a0 <= np.finfo(float).eps * amplitude:
        raise ValueError("initial fluctuation normalization unresolved")
    energy0 = length * a0 * a0 / 2
    wave = 2 * np.pi * np.fft.fftfreq(u.shape[1], d=length / u.shape[1])

    def trajectory(w):
        grad = np.fft.ifft(np.fft.fft(w, axis=1) * (1j * wave), axis=1).real
        e = 0.5 * length * np.mean((w - w.mean(axis=1)[:, None]) ** 2, axis=1)
        d = viscosity * length * np.mean(grad * grad, axis=1)
        integral = np.concatenate(([0.0], np.cumsum((d[:-1] + d[1:]) * np.diff(t) / 2)))
        balance = e - e[0] + integral
        return e, d, balance, grad

    e, d, b, g = trajectory(u)
    er, dr, br, gr = trajectory(v)
    field = float(np.sqrt(time_average(np.mean((u - v) ** 2, axis=1), t)) / a0)
    energy = float(np.sqrt(time_average(((e - er) / energy0) ** 2, t)))
    x = np.arange(u.shape[1]) * length / u.shape[1]
    weak = []
    # Actual test-function weak formulation: integrate u_t*phi, and integrate
    # spatial derivatives by parts. Only four modes: diagnostic, not a PDE proof.
    for mode in range(1, 5):
        k = mode * 2 * np.pi / length
        for phi, phix in (
            (np.sin(k * x), k * np.cos(k * x)),
            (np.cos(k * x), -k * np.sin(k * x)),
        ):
            phixx = -k * k * phi
            flux = np.mean(-0.5 * u * u * phix - viscosity * u * phixx, axis=1)
            residual = (
                np.mean(np.diff(u, axis=0) * phi, axis=1)
                + (flux[:-1] + flux[1:]) * np.diff(t) / 2
            )
            weak.extend(
                (residual / (amplitude * np.diff(t) / characteristic_time)) ** 2
            )
    result = {
        "version": VERSION,
        "metrics": {
            "energy_path_max": float(np.max(np.abs(e - er)) / energy0),
            "field_time_rms": field,
            "energy_path_rms": energy,
            "initial_condition": float(np.max(np.abs(u[0] - u0)) / amplitude),
            "conserved_mean": float(
                np.max(np.abs(u.mean(axis=1) - u0.mean())) / amplitude
            ),
            "maximum_principle": float(
                max(0.0, np.max(u) - np.max(u0), np.min(u0) - np.min(u)) / amplitude
            ),
            "integrated_energy_balance": float(np.max(np.abs(b)) / energy0),
        },
        "reference_balance_discretization_indicator": float(
            np.max(np.abs(br)) / energy0
        ),
        "diagnostics": {
            "positive_sampled_energy_increment": float(
                max(0.0, np.max(np.diff(e))) / energy0
            ),
            "fourier_weak_test_residual": float(np.sqrt(np.mean(weak))),
            "periodic_closure": "ENFORCED_BY_REPRESENTATION_NO_QUALITY_CREDIT",
            "candidate_half_time": crossing(e, t, energy0 / 2),
            "reference_half_time": crossing(er, t, energy0 / 2),
            "candidate_compression_time_index": int(np.argmax(np.max(-g, axis=1))),
            "reference_compression_time_index": int(np.argmax(np.max(-gr, axis=1))),
            "candidate_peak_dissipation_time_index": int(np.argmax(d)),
            "reference_peak_dissipation_time_index": int(np.argmax(dr)),
            "candidate_energy_final_over_initial": float(e[-1] / energy0),
            "reference_energy_final_over_initial": float(er[-1] / energy0),
            "time_count": len(t),
            "space_count": u.shape[1],
        },
    }
    if any(not math.isfinite(x) or x < 0 for x in result["metrics"].values()):
        raise ValueError("nonfinite derived observation")
    return result

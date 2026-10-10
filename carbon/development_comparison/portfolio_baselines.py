"""Offline public DEVELOPMENT comparators; no solver or dispatch capabilities.

Run with an explicitly byte-pinned neutral panel and companion materials.
The shared task judge owns limits, units, selection and reference resolution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy

from carbon.design_search import producer_panels, tasks
from carbon.development_comparison import cheap_baselines as cb

SCHEMA = "carbon.development-comparator-materials.v1"
FAMILIES = ("cooling-cell", "f02", "f08", "f13")
COST_FIELDS = (
    "original_acquisition_cpu_s",
    "reference_refinement_cpu_s",
    "retained_verification_cpu_s",
    "peak_process_ram_bytes",
    "money_eur",
)


def _shape(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError("closed comparator material shape required")


def _hash(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("exact SHA256 material identity required")


def _numbers(value, dimensions):
    a = cb._finite_array(value, dimensions)
    if a.size == 0 or a.size > 2_000_000:
        raise ValueError("nonempty bounded numerical material required")
    return a


def _positive(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("positive finite physical input required")
    return float(value)


def seal_materials(body):
    """Producer byte preparation, not adequacy/rights approval."""
    return {**body, "materials_digest": tasks.digest(body)}


@dataclass(frozen=True, init=False)
class Materials:
    """Construct only through validate_materials, not by asserting a flag."""

    body_json: str

    def __init__(self, *args, **kwargs):
        raise TypeError("use validate_materials")

    @property
    def body(self):
        return json.loads(self.body_json)


def validate_materials(export, material):
    producer_panels.adapt_export(export)
    if export["family"] not in FAMILIES:
        raise ValueError("ticket owns four portfolio comparator families only")
    _shape(
        material,
        (
            "schema",
            "family",
            "scope",
            "export_digest",
            "observer_versions",
            "settings",
            "rows",
            "costs",
            "materials_digest",
        ),
    )
    if (
        material["schema"] != SCHEMA
        or material["family"] != export["family"]
        or material["scope"] not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
        or material["export_digest"] != export["export_digest"]
        or material["materials_digest"]
        != tasks.digest({k: v for k, v in material.items() if k != "materials_digest"})
    ):
        raise ValueError("matched public-development material identity required")
    observers = set()
    quantities = {}
    for entry in export["questions"]:
        for band, task, _ in cb._panels(entry):
            if band is not None or task["schema"] != tasks.RUNNABLE_SCHEMA:
                raise ValueError("four-family runnable non-indexed tasks required")
            observers.add(task["identity"]["observer_version"])
            for q in [
                task["objective"],
                *task["limits"],
                *([task["secondary"]] if task["secondary"] else []),
            ]:
                name, unit = q["quantity"], q["unit"]
                if name in quantities and quantities[name] != unit:
                    raise ValueError("inconsistent quantity unit")
                quantities[name] = unit
    if material["observer_versions"] != sorted(observers):
        raise ValueError("material observer versions do not match task")
    _shape(material["settings"], ("coordinate_fields", "lags", "reducers"))
    settings = material["settings"]
    fields = settings["coordinate_fields"]
    if (
        type(fields) is not list
        or not fields
        or len(set(fields)) != len(fields)
        or any(type(f) is not str for f in fields)
    ):
        raise ValueError("ordered physical action coordinate fields required")
    if type(settings["lags"]) is not int or not 1 <= settings["lags"] <= 128:
        raise ValueError("bounded preselected FIR lag count required")
    reducers = settings["reducers"]
    if type(reducers) is not list or not reducers:
        raise ValueError("explicit quantity reducers required")
    names = set()
    allowed = {
        "cooling-cell": {"surface"},
        "f02": {"temperature_max", "temperature_final_max", "extra_energy_j"},
        "f08": {"dynamic_peak", "static_max", "input_scalar"},
        "f13": {"interval_p10_tl_db", "minimum_tl_db", "input_scalar"},
    }[export["family"]]
    for r in reducers:
        _shape(r, ("quantity", "unit", "kind"))
        if (
            r["quantity"] in names
            or quantities.get(r["quantity"]) != r["unit"]
            or r["kind"] not in allowed
        ):
            raise ValueError("matched quantity/unit/method reducer required")
        expected_units = {
            "extra_energy_j": {"J"},
            "temperature_max": {"C", "degC", "°C"},
            "temperature_final_max": {"C", "degC", "°C"},
            "interval_p10_tl_db": {"dB"},
            "minimum_tl_db": {"dB"},
        }
        if r["kind"] in expected_units and r["unit"] not in expected_units[r["kind"]]:
            raise ValueError("fixed physical reducer unit differs")
        names.add(r["quantity"])
    if names != set(quantities):
        raise ValueError("all objective and limit quantities require reducers")
    _shape(material["costs"], COST_FIELDS)
    for value in material["costs"].values():
        if value is not None and (
            type(value) not in (int, float) or not math.isfinite(value) or value < 0
        ):
            raise ValueError("cost is measured nonnegative number or null")
    physical = cb._physical_rows(export)
    index = {(r["candidate"], r["condition"]): r for r in physical}
    if (
        type(material["rows"]) is not list
        or not 1 <= len(material["rows"]) <= 4096
        or len(material["rows"]) != len(index)
    ):
        raise ValueError("exactly one material row per physical observation required")
    seen = set()
    witness_sources = {
        r.get("reference_source_sha256") for r in material["rows"] if type(r) is dict
    }
    for r in material["rows"]:
        _shape(
            r,
            (
                "candidate",
                "condition",
                "context_sha256",
                "coordinates",
                "reference_source_sha256",
                "calibration_source_sha256",
                "payload",
            ),
        )
        key = (r["candidate"], r["condition"])
        if key not in index or key in seen:
            raise ValueError("duplicate or unmatched material row")
        seen.add(key)
        _hash(r["context_sha256"])
        _hash(r["reference_source_sha256"])
        _hash(r["calibration_source_sha256"])
        action = index[key]["action"]
        if any(f not in action for f in fields):
            raise ValueError("physical coordinate absent from registered action")
        coordinates = _numbers(r["coordinates"], 1)
        if len(coordinates) != len(fields) or coordinates.tolist() != [
            action[f] for f in fields
        ]:
            raise ValueError("coordinates must be physical registered action values")
        if (
            export["family"] in ("f02", "f08")
            and r["calibration_source_sha256"] in witness_sources
        ):
            raise ValueError("calibration must be independent of response witness")
        _validate_payload(export["family"], r["payload"], reducers)
        if export["family"] != "cooling-cell":
            p = r["payload"]
            witness = (
                np.asarray(p["temperature_c"])
                if export["family"] == "f02"
                else (
                    np.asarray(p["response_real"]) + 1j * np.asarray(p["response_imag"])
                    if export["family"] == "f08"
                    else np.asarray(p["tl_db"])
                )
            )
            reduced = _reduce(export["family"], p, witness, reducers)
            if any(
                not math.isclose(v, index[key]["values"][q], rel_tol=1e-9, abs_tol=1e-9)
                for q, v in reduced.items()
            ):
                raise ValueError(
                    "witness reduction differs from registered observer values"
                )
    verified = object.__new__(Materials)
    object.__setattr__(
        verified, "body_json", json.dumps(material, sort_keys=True, allow_nan=False)
    )
    return verified


def _validate_payload(family, p, reducers):
    if family == "cooling-cell":
        _shape(p, ())
        return
    if family == "f02":
        _shape(
            p, ("time_s", "extra_power_w", "baseline_temperature_c", "temperature_c")
        )
        t = _numbers(p["time_s"], 1)
        dt = np.diff(t)
        if len(t) < 3 or t[0] != 0 or np.any(dt <= 0) or not np.allclose(dt, dt[0]):
            raise ValueError(
                "uniform event-aligned FIR time grid starting at zero required"
            )
        power = _numbers(p["extra_power_w"], 2)
        base = _numbers(p["baseline_temperature_c"], 2)
        truth = _numbers(p["temperature_c"], 2)
        if (
            power.shape != (len(t), 2)
            or np.any(power < 0)
            or base.shape != truth.shape
            or len(base) != len(t)
        ):
            raise ValueError(
                "two patch inputs and aligned retained spatial traces required"
            )
    elif family == "f08":
        _shape(
            p,
            (
                "frequency_hz",
                "mode_hz",
                "damping_ratio",
                "residue_real",
                "residue_imag",
                "static_residual_real",
                "static_residual_imag",
                "static_compliance",
                "input_scalars",
                "response_real",
                "response_imag",
            ),
        )
        f = _numbers(p["frequency_hz"], 1)
        modes = _numbers(p["mode_hz"], 1)
        _positive(p["damping_ratio"])
        residues = _numbers(p["residue_real"], 2)
        imaginary = _numbers(p["residue_imag"], 2)
        residual = _numbers(p["static_residual_real"], 1)
        residual_i = _numbers(p["static_residual_imag"], 1)
        static = _numbers(p["static_compliance"], 1)
        response = _numbers(p["response_real"], 2)
        response_i = _numbers(p["response_imag"], 2)
        if (
            np.any(f <= 0)
            or np.any(np.diff(f) <= 0)
            or np.any(modes <= 0)
            or residues.shape != imaginary.shape
            or residues.shape[1] != len(modes)
            or len(residual) != residues.shape[0]
            or len(residual_i) != len(residual)
            or len(static) != len(residual)
            or response.shape != response_i.shape
            or response.shape != (len(f), len(residual))
        ):
            raise ValueError(
                "aligned geometry-specific complex modal/probe grids required"
            )
        _scalar_inputs(p, reducers)
    else:
        _shape(
            p,
            (
                "frequency_hz",
                "rho_kg_m3",
                "sound_speed_m_s",
                "port_radius_m",
                "coaxial",
                "mean_flow_m_s",
                "segments",
                "input_scalars",
                "tl_db",
            ),
        )
        f = _numbers(p["frequency_hz"], 1)
        _positive(p["rho_kg_m3"])
        _positive(p["sound_speed_m_s"])
        _positive(p["port_radius_m"])
        if np.any(f <= 0) or np.any(np.diff(f) <= 0) or len(f) < 2:
            raise ValueError("ordered complete frequency grid required")
        if type(p["coaxial"]) is not bool or type(p["mean_flow_m_s"]) not in (
            int,
            float,
        ):
            raise ValueError("explicit geometry and flow scope required")
        if not math.isfinite(p["mean_flow_m_s"]):
            raise ValueError("finite flow required")
        if type(p["segments"]) is not list or not 1 <= len(p["segments"]) <= 128:
            raise ValueError("bounded rigid circular segment chain required")
        for s in p["segments"]:
            _shape(s, ("length_m", "radius_m"))
            _positive(s["length_m"])
            _positive(s["radius_m"])
        if _numbers(p["tl_db"], 1).shape != f.shape:
            raise ValueError("matched full-curve witness required")
        _scalar_inputs(p, reducers)


def _scalar_inputs(p, reducers):
    expected = {r["quantity"] for r in reducers if r["kind"] == "input_scalar"}
    _shape(p["input_scalars"], expected)
    if expected:
        _numbers(list(p["input_scalars"].values()), 1)


def fir_features(power, lags):
    """Causal discrete convolution for two extra-power patches, zero prehistory."""
    u = _numbers(power, 2)
    if u.shape[1] != 2 or type(lags) is not int or not 1 <= lags <= 128:
        raise ValueError("two patch power series and bounded lags required")
    if len(u) * 2 * lags > 2_000_000:
        raise cb.Unsupported("bounded FIR feature matrix exceeded")
    x = np.zeros((len(u), 2 * lags))
    for patch in range(2):
        for lag in range(lags):
            if lag < len(u):
                x[lag:, patch * lags + lag] = u[: len(u) - lag, patch]
    return x


def fit_impulse(training, target, lags):
    """Fit on other complete waveforms only, never target temperatures."""
    if not training:
        raise cb.Unsupported("no other waveform calibration")
    if sum(len(r["time_s"]) * 2 * lags for r in training) > 2_000_000:
        raise cb.Unsupported("bounded FIR calibration matrix exceeded")
    for r in training:
        if (
            r["time_s"] != target["time_s"]
            or np.asarray(r["temperature_c"]).shape
            != np.asarray(target["baseline_temperature_c"]).shape
            or r["baseline_temperature_c"] != target["baseline_temperature_c"]
        ):
            raise cb.Unsupported("FIR context/grid differs")
    x = np.concatenate([fir_features(r["extra_power_w"], lags) for r in training])
    y = np.concatenate(
        [
            np.asarray(r["temperature_c"]) - np.asarray(r["baseline_temperature_c"])
            for r in training
        ]
    )
    if np.linalg.matrix_rank(x) != x.shape[1]:
        raise cb.Unsupported("two-source FIR calibration is rank deficient")
    coefficients, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
    # Avoid untested amplitude extrapolation. Linearity itself is not qualified.
    maximum = np.max(np.concatenate([r["extra_power_w"] for r in training]), axis=0)
    if np.any(np.max(target["extra_power_w"], axis=0) > maximum):
        raise cb.Unsupported("outside retained input amplitude support")
    return (
        np.asarray(target["baseline_temperature_c"])
        + fir_features(target["extra_power_w"], lags) @ coefficients
    )


def modal_response(p):
    """Retained mass-normalized complex residues, same-geometry modal cache."""
    omega = 2 * np.pi * np.asarray(p["frequency_hz"])
    modes = 2 * np.pi * np.asarray(p["mode_hz"])
    if len(omega) * len(modes) > 2_000_000:
        raise cb.Unsupported("bounded modal response matrix exceeded")
    residues = np.asarray(p["residue_real"]) + 1j * np.asarray(p["residue_imag"])
    denominator = (
        modes[None, :] ** 2
        - omega[:, None] ** 2
        + 2j * p["damping_ratio"] * omega[:, None] * modes[None, :]
    )
    residual = np.asarray(p["static_residual_real"]) + 1j * np.asarray(
        p["static_residual_imag"]
    )
    return (1 / denominator) @ residues.T + residual


def transfer_curve(p):
    """Rigid coaxial lossless chain, volume-velocity ports, exp(+i omega t)."""
    c, rho = p["sound_speed_m_s"], p["rho_kg_m3"]
    f = np.asarray(p["frequency_hz"])
    radii = [p["port_radius_m"], *[s["radius_m"] for s in p["segments"]]]
    cutoff = c * 1.841 / (2 * np.pi * max(radii))
    if not p["coaxial"] or p["mean_flow_m_s"] != 0 or f[-1] >= cutoff:
        raise cb.Unsupported("requires coaxial/no-flow/below first transverse cutoff")
    chain = np.tile(np.eye(2, dtype=complex), (len(f), 1, 1))
    for s in p["segments"]:
        angle = 2 * np.pi * f * s["length_m"] / c
        z = rho * c / (np.pi * s["radius_m"] ** 2)
        m = np.empty_like(chain)
        m[:, 0, 0] = m[:, 1, 1] = np.cos(angle)
        m[:, 0, 1], m[:, 1, 0] = 1j * z * np.sin(angle), 1j * np.sin(angle) / z
        chain = chain @ m
    z_port = rho * c / (np.pi * p["port_radius_m"] ** 2)
    amplitude = (
        chain[:, 0, 0]
        + chain[:, 0, 1] / z_port
        + chain[:, 1, 0] * z_port
        + chain[:, 1, 1]
    )
    return 10 * np.log10(np.abs(amplitude) ** 2 / 4)


def interval_p10(frequencies, values):
    """Trapezoidal frequency-interval weights, not counts on an adaptive grid."""
    f, y = np.asarray(frequencies), np.asarray(values)
    weights = np.zeros(len(f))
    weights[:-1] += np.diff(f) / 2
    weights[1:] += np.diff(f) / 2
    order = np.argsort(y, kind="stable")
    index = np.searchsorted(np.cumsum(weights[order]), 0.1 * weights.sum(), side="left")
    return float(y[order[index]])


def _reduce(family, payload, curve, reducers):
    out = {}
    for r in reducers:
        kind = r["kind"]
        if kind in ("temperature_max", "dynamic_peak"):
            value = (
                float(np.max(np.abs(curve)))
                if kind == "dynamic_peak"
                else float(np.max(curve))
            )
        elif kind == "temperature_final_max":
            value = float(np.max(curve[-1]))
        elif kind == "extra_energy_j":
            value = float(
                np.sum(np.asarray(payload["extra_power_w"])[:-1])
                * (payload["time_s"][1] - payload["time_s"][0])
            )
        elif kind == "static_max":
            value = float(np.max(np.abs(payload["static_compliance"])))
        elif kind == "interval_p10_tl_db":
            value = interval_p10(payload["frequency_hz"], curve)
        elif kind == "minimum_tl_db":
            value = float(np.min(curve))
        elif kind == "input_scalar":
            value = float(payload["input_scalars"][r["quantity"]])
        else:
            raise cb.Unsupported("unsupported retained observable")
        if not math.isfinite(value):
            raise cb.Unsupported("nonfinite reduced observable")
        out[r["quantity"]] = value
    return out


def _curve_errors(errors):
    if not errors:
        return {"samples": 0, "mae": None, "rmse": None, "max_abs": None}
    e = np.concatenate(errors)
    return {
        "samples": int(e.size),
        "mae": float(np.mean(np.abs(e))),
        "rmse": float(np.sqrt(np.mean(np.abs(e) ** 2))),
        "max_abs": float(np.max(np.abs(e))),
    }


def _predict(export, material):
    if not isinstance(material, Materials):
        raise TypeError("validated Materials required")
    material = material.body
    family = export["family"]
    rows = material["rows"]
    settings = material["settings"]
    physical = {(r["candidate"], r["condition"]): r for r in cb._physical_rows(export)}
    groups = sorted({tuple(r["coordinates"]) for r in rows})
    predictions, reasons, costs, curve_errors, folds = {}, [], [], [], []
    for group in groups:
        held = [r for r in rows if tuple(r["coordinates"]) == group]
        training = [r for r in rows if tuple(r["coordinates"]) != group]
        folds.append(
            {
                "held_action_coordinates": list(group),
                "held_rows": len(held),
                "training_rows": len(training),
                "uses_training_rows": family in ("cooling-cell", "f02"),
            }
        )
        for target in held:
            t0, c0 = time.perf_counter(), time.process_time()
            key = (None, target["candidate"], target["condition"])
            try:
                peers = [
                    r
                    for r in training
                    if r["context_sha256"] == target["context_sha256"]
                ]
                payload = target["payload"]
                if family == "cooling-cell":
                    names = [r["quantity"] for r in settings["reducers"]]
                    if len(peers) < 2:
                        raise cb.Unsupported("insufficient same-context geometry rows")
                    unique = {}
                    for r in peers:
                        point = tuple(r["coordinates"])
                        values = [
                            physical[(r["candidate"], r["condition"])]["values"][q]
                            for q in names
                        ]
                        if point in unique and unique[point] != values:
                            raise ValueError("same context/geometry changed truth")
                        unique[point] = values
                    if len(unique) < 2:
                        raise cb.Unsupported(
                            "insufficient unique same-context geometries"
                        )
                    surface = cb.CurveSurface(list(unique), list(unique.values()))
                    result = dict(
                        zip(
                            names,
                            map(float, surface.predict([target["coordinates"]])[0]),
                        )
                    )
                else:
                    if family == "f02":
                        curve = fit_impulse(
                            [r["payload"] for r in peers], payload, settings["lags"]
                        )
                        truth = np.asarray(payload["temperature_c"])
                    elif family == "f08":
                        curve = modal_response(payload)
                        truth = np.asarray(payload["response_real"]) + 1j * np.asarray(
                            payload["response_imag"]
                        )
                    else:
                        curve = transfer_curve(payload)
                        truth = np.asarray(payload["tl_db"])
                    result = _reduce(family, payload, curve, settings["reducers"])
                    # Diagnostic witness access occurs only AFTER prediction.
                    curve_errors.append((curve - truth).ravel())
                if not all(math.isfinite(v) for v in result.values()):
                    raise cb.Unsupported("nonfinite comparator output")
                predictions[key] = result
            except cb.Unsupported as error:
                reasons.append(
                    {
                        "candidate": target["candidate"],
                        "condition": target["condition"],
                        "reason": str(error),
                    }
                )
            costs.append(
                {"cpu_s": time.process_time() - c0, "wall_s": time.perf_counter() - t0}
            )
    return predictions, {
        "folds": folds,
        "abstention_reasons": reasons,
        "fit_reduction_query_cost": cb._cost(costs),
        "curve_errors": _curve_errors(curve_errors),
    }


def measure(export, *, material=None):
    """Descriptive evidence only. No threshold/power/qualification decision."""
    producer_panels.adapt_export(export)
    if export["family"] not in FAMILIES:
        raise ValueError("unsupported portfolio family")
    report = {
        "schema": "carbon.development-portfolio-baseline-report.v1",
        "family": export["family"],
        "export_digest": export["export_digest"],
        "material": "DEVELOPMENT",
        "reference_solves_launched": 0,
        "carbon_arm": "NOT_SUPPLIED",
        "v4_disposition": "UNRESOLVED_NO_MATCHED_CARBON_ARM",
        "claims": {
            "physical_safety": False,
            "qualified_uncertainty": False,
            "tested_challenge": False,
        },
    }
    if material is None:
        report["held_out"] = {"status": "HOLD_MISSING_COMPARATOR_MATERIALS"}
        return report
    verified = validate_materials(export, material)
    predicted, diagnostics = _predict(export, verified)
    exact = {
        (r["band"], r["candidate"], r["condition"]): r["values"]
        for r in cb._physical_rows(export)
    }
    report["closed_bank"] = {
        "interpretation": "arithmetic lookup replay, not generalization",
        "pointwise": cb.pointwise_errors(export, exact),
        "decision": cb.decision_report(export, exact),
    }
    report["held_out"] = {
        "status": "MEASURED" if predicted else "HOLD_NO_SUPPORTED_PREDICTIONS",
        "pointwise": cb.pointwise_errors(export, predicted),
        "decision": cb.decision_report(export, predicted),
        **diagnostics,
    }
    report["fold_interpretation"] = {
        "cooling-cell": "leave-geometry-out across sibling conditions; same-context interpolation only",
        "f02": "leave-waveform-action-out across contexts; independent baseline and other waveform calibration",
        "f08": "held-out response curves with independently acquired same-geometry modes; NOT new-geometry generalization",
        "f13": "unfitted geometry predictions; plane-wave scope only; missing multimode comparator arm",
    }[export["family"]]
    report["costs"] = {
        k: {"status": "NOT_MEASURED" if v is None else "PRODUCER_REPORTED", "value": v}
        for k, v in material["costs"].items()
    }
    report["costs"]["Carbon_rebuild_inference"] = {
        "status": "NOT_MEASURED",
        "value": None,
    }
    report["materials_digest"] = material["materials_digest"]
    return report


def _read(path, expected):
    _hash(expected)
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("bounded input exceeds 32 MiB")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("approved public DEVELOPMENT byte identity differs")
    return json.loads(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--materials", type=Path, required=True)
    parser.add_argument("--materials-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    t0, c0 = time.perf_counter(), time.process_time()
    report = measure(
        _read(args.panel, args.expected_sha256),
        material=_read(args.materials, args.materials_sha256),
    )
    report["input_sha256"] = args.expected_sha256
    report["materials_sha256"] = args.materials_sha256
    report["comparator_source_sha256"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    report["environment"] = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "platform": platform.platform(),
        "canonical": False,
    }
    report["read_validation_measure_cpu_s"] = time.process_time() - c0
    report["read_validation_measure_wall_s"] = time.perf_counter() - t0
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, sort_keys=True, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "family": report["family"],
                "output": str(args.output),
                "reference_solves_launched": 0,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

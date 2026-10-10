"""Public DEVELOPMENT parametric ROM comparators; never a reference runner.

Common-basis operators must be independently prepared and paid for in the
ledger. This module does not assemble FE systems, discover data or qualify ROMs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.spatial import Delaunay, QhullError

from carbon.design_search import producer_panels, tasks
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import portfolio_baselines as pb

SCHEMA = "carbon.development-reduced-operators.v1"
COST_FIELDS = (
    *pb.COST_FIELDS,
    "operator_assembly_projection_cpu_s",
    "basis_alignment_cpu_s",
)


@dataclass(frozen=True, init=False)
class Operators:
    body_json: str

    def __init__(self, *args, **kwargs):
        raise TypeError("use validate_operators")

    @property
    def body(self):
        return json.loads(self.body_json)


def seal_operators(body):
    return {**body, "operators_digest": tasks.digest(body)}


def matrix(value, shape=None):
    a = pb._numbers(value, 2)
    if any(n > 128 for n in a.shape) or (shape is not None and a.shape != shape):
        raise ValueError("bounded matched reduced matrix required")
    return a


def positive_matrix(value, n, *, definite):
    a = matrix(value, (n, n))
    if not np.allclose(a, a.T, atol=1e-12, rtol=1e-12):
        raise ValueError("symmetric reduced operator required")
    eigen = np.linalg.eigvalsh(a)
    if eigen.min() <= 0 if definite else eigen.min() < 0:
        raise ValueError("positive reduced operator required")
    return a


def complex_array(real, imag, shape):
    a, b = pb._numbers(real, len(shape)), pb._numbers(imag, len(shape))
    if a.shape != shape or b.shape != shape:
        raise ValueError("matched complex query/witness shape required")
    return a + 1j * b


def validate_operators(export, body):
    producer_panels.adapt_export(export)
    pb._shape(
        body,
        (
            "schema",
            "family",
            "scope",
            "export_digest",
            "coordinate_fields",
            "reducers",
            "rows",
            "costs",
            "operators_digest",
        ),
    )
    if (
        export["family"] not in ("f08", "f13")
        or body["schema"] != SCHEMA
        or body["family"] != export["family"]
        or body["scope"] not in ("SYNTHETIC_FIXTURE", "PUBLIC_DEVELOPMENT")
        or body["export_digest"] != export["export_digest"]
        or body["operators_digest"]
        != tasks.digest({k: v for k, v in body.items() if k != "operators_digest"})
    ):
        raise ValueError("matched public reduced-operator identity required")
    fields = body["coordinate_fields"]
    if (
        type(fields) is not list
        or not 1 <= len(fields) <= 12
        or len(set(fields)) != len(fields)
        or any(type(f) is not str for f in fields)
    ):
        raise ValueError("ordered physical action fields required")
    quantities, observers = {}, {}
    for entry in export["questions"]:
        for band, task, reference in cb._panels(entry):
            if band is not None or task["schema"] != tasks.RUNNABLE_SCHEMA:
                raise ValueError("two-family non-indexed runnable tasks required")
            for row in reference:
                key = row["candidate"], row["condition"]
                version = task["identity"]["observer_version"]
                if key in observers and observers[key] != version:
                    raise ValueError("physical observation has differing observers")
                observers[key] = version
            for q in (
                task["objective"],
                *task["limits"],
                *([task["secondary"]] if task["secondary"] else []),
            ):
                if (
                    q["quantity"] in quantities
                    and quantities[q["quantity"]] != q["unit"]
                ):
                    raise ValueError("inconsistent quantity units")
                quantities[q["quantity"]] = q["unit"]
    allowed = {
        "f08": {"dynamic_peak", "static_peak", "input_scalar"},
        "f13": {"interval_p10_tl_db", "minimum_tl_db", "input_scalar"},
    }[body["family"]]
    reducers = body["reducers"]
    if type(reducers) is not list or len(reducers) != len(quantities):
        raise ValueError("complete quantity reducer mapping required")
    for r in reducers:
        pb._shape(r, ("quantity", "unit", "kind"))
        if quantities.get(r["quantity"]) != r["unit"] or r["kind"] not in allowed:
            raise ValueError("matched quantity/unit reducer required")
        units = {
            "dynamic_peak": {"m/N", "mm/N"},
            "static_peak": {"m/N", "mm/N"},
            "interval_p10_tl_db": {"dB"},
            "minimum_tl_db": {"dB"},
        }
        if r["kind"] in units and r["unit"] not in units[r["kind"]]:
            raise ValueError("fixed ROM observable units required")
    if {r["quantity"] for r in reducers} != set(quantities):
        raise ValueError("duplicate or missing reducer")
    pb._shape(body["costs"], COST_FIELDS)
    for value in body["costs"].values():
        if value is not None and (
            type(value) not in (int, float) or not math.isfinite(value) or value < 0
        ):
            raise ValueError("measured nonnegative cost or null required")
    physical = {(r["candidate"], r["condition"]): r for r in cb._physical_rows(export)}
    rows = body["rows"]
    if (
        type(rows) is not list
        or not 1 <= len(rows) <= 1024
        or len(rows) != len(physical)
    ):
        raise ValueError("one bounded operator row per physical observation required")
    witnesses = {r.get("witness_source_sha256") for r in rows if type(r) is dict}
    seen, layouts = set(), {}
    for row in rows:
        pb._shape(
            row,
            (
                "candidate",
                "condition",
                "coordinates",
                "context_sha256",
                "basis_sha256",
                "basis_source_sha256",
                "basis_training_coordinates",
                "observer_version",
                "calibration_source_sha256",
                "query_source_sha256",
                "witness_source_sha256",
                "model",
                "query",
                "witness",
            ),
        )
        key = row["candidate"], row["condition"]
        if key in seen or key not in physical:
            raise ValueError("unique matched operator row required")
        seen.add(key)
        for field in (
            "context_sha256",
            "basis_sha256",
            "basis_source_sha256",
            "calibration_source_sha256",
            "query_source_sha256",
            "witness_source_sha256",
        ):
            pb._hash(row[field])
        if (
            row["calibration_source_sha256"] in witnesses
            or row["query_source_sha256"] in witnesses
            or row["basis_source_sha256"] in witnesses
        ):
            raise ValueError(
                "calibration/query inputs must be independent of response witnesses"
            )
        record = physical[key]
        if row["observer_version"] != observers[key]:
            raise ValueError("matched observer version required")
        x = pb._numbers(row["coordinates"], 1)
        if len(x) != len(fields) or x.tolist() != [
            record["action"].get(f) for f in fields
        ]:
            raise ValueError("registered physical coordinates required")
        provenance = row["basis_training_coordinates"]
        if type(provenance) is not list or len(provenance) > 1024:
            raise ValueError("bounded basis training provenance required")
        for point in provenance:
            if pb._numbers(point, 1).shape != x.shape:
                raise ValueError("physical basis training coordinates required")
        validate_model_query(body["family"], row, reducers)
        model = row["model"]
        layout = {
            name: np.asarray(value).shape
            for name, value in model.items()
            if name not in ("port_sides", "rho_kg_m3", "sound_speed_m_s")
        }
        layout.update(
            {
                name: model[name]
                for name in ("port_sides", "rho_kg_m3", "sound_speed_m_s")
                if name in model
            }
        )
        layout["basis_source"] = row["basis_source_sha256"]
        layout["basis_training"] = provenance
        layout_key = row["context_sha256"], row["basis_sha256"], row["observer_version"]
        if layout_key in layouts and layouts[layout_key] != layout:
            raise ValueError(
                "common basis/fluid/port/output layout or provenance differs"
            )
        layouts[layout_key] = layout
        values = reduce_observables(
            body["family"], row["query"], row["witness"], reducers
        )
        if any(
            not math.isclose(values[q], record["values"][q], rel_tol=1e-9, abs_tol=1e-9)
            for q in values
        ):
            raise ValueError("witness reduction differs from registered observer")
    verified = object.__new__(Operators)
    object.__setattr__(
        verified, "body_json", json.dumps(body, sort_keys=True, allow_nan=False)
    )
    return verified


def validate_model_query(family, row, reducers):
    model, query, witness = row["model"], row["query"], row["witness"]
    common = ("K", "M", "C")
    pb._shape(
        model,
        common
        + (
            ("B", "L")
            if family == "f08"
            else ("ports", "cutoff_m_inv", "port_sides", "rho_kg_m3", "sound_speed_m_s")
        ),
    )
    n = len(matrix(model["M"]))
    positive_matrix(model["M"], n, definite=True)
    positive_matrix(model["K"], n, definite=family == "f08")
    positive_matrix(model["C"], n, definite=False)
    pb._shape(
        query,
        (
            ("frequency_hz", "input_scalars")
            if family == "f08"
            else (
                "frequency_hz",
                "incident_real",
                "incident_imag",
                "mean_flow_m_s",
                "input_scalars",
            )
        ),
    )
    f = pb._numbers(query["frequency_hz"], 1)
    if len(f) > 4096 or f[0] <= 0 or np.any(np.diff(f) <= 0):
        raise ValueError("bounded increasing positive frequency grid required")
    if family == "f08":
        pb._shape(query, ("frequency_hz", "input_scalars"))
        pb._shape(witness, ("response_real", "response_imag", "static_m_per_n"))
        b, l = matrix(model["B"]), matrix(model["L"])
        if b.shape != (n, 1) or l.shape[1] != n:
            raise ValueError("unit-force structural load/output mapping required")
        complex_array(
            witness["response_real"], witness["response_imag"], (len(f), l.shape[0])
        )
        if pb._numbers(witness["static_m_per_n"], 1).shape != (l.shape[0],):
            raise ValueError("matched static witness required")
    else:
        pb._shape(
            query,
            (
                "frequency_hz",
                "incident_real",
                "incident_imag",
                "mean_flow_m_s",
                "input_scalars",
            ),
        )
        pb._shape(witness, ("tl_db",))
        ports = matrix(model["ports"])
        m = ports.shape[1]
        cutoff = pb._numbers(model["cutoff_m_inv"], 1)
        if ports.shape[0] != n or cutoff.shape != (m,) or np.any(cutoff < 0):
            raise ValueError("matched modal ports and cutoffs required")
        sides = model["port_sides"]
        if (
            type(sides) is not list
            or len(sides) != m
            or set(sides) != {"inlet", "outlet"}
        ):
            raise ValueError("declared inlet/outlet modal ordering required")
        incident = complex_array(
            query["incident_real"], query["incident_imag"], (len(f), m)
        )
        if query["mean_flow_m_s"] != 0 or np.any(
            incident[:, np.asarray(sides) == "outlet"] != 0
        ):
            raise ValueError("no-flow inlet-only incident acoustic scope required")
        pb._positive(model["rho_kg_m3"])
        pb._positive(model["sound_speed_m_s"])
        if pb._numbers(witness["tl_db"], 1).shape != (len(f),):
            raise ValueError("matched full-curve witness required")
    scalar_names = {r["quantity"] for r in reducers if r["kind"] == "input_scalar"}
    pb._shape(query["input_scalars"], scalar_names)
    for v in query["input_scalars"].values():
        if type(v) not in (int, float) or not math.isfinite(v):
            raise ValueError("finite independently sourced input scalar required")


def interpolate(peers, target):
    """Simplex convex interpolation, not unconstrained modal-label interpolation."""
    unique = {}
    for row in peers:
        if row["basis_sha256"] != target["basis_sha256"]:
            continue
        if target["coordinates"] in row.get("basis_training_coordinates", []):
            continue
        x = tuple(row["coordinates"])
        if x in unique and unique[x]["model"] != row["model"]:
            raise ValueError("same-context geometry has differing projected operators")
        unique[x] = row
    anchors = list(unique.values())
    x = np.asarray([r["coordinates"] for r in anchors], dtype=float)
    point = np.asarray(target["coordinates"], dtype=float)
    d = len(point)
    if len(anchors) < d + 1:
        raise cb.Unsupported("insufficient common-basis independent geometries")
    span = np.ptp(x, axis=0)
    if np.any(span == 0):
        raise cb.Unsupported("degenerate geometry support")
    points, p = (x - x.min(axis=0)) / span, (point - x.min(axis=0)) / span
    if d == 1:
        order = np.argsort(points[:, 0])
        k = np.searchsorted(points[order, 0], p[0])
        if k == 0 or k == len(order):
            raise cb.Unsupported("geometry outside training hull")
        selected = order[k - 1 : k + 1]
        left, right = points[selected, 0]
        alpha = (p[0] - left) / (right - left)
        weights = np.asarray([1 - alpha, alpha])
    else:
        try:
            hull = Delaunay(points)
            simplex = hull.find_simplex(p)
        except QhullError as error:
            raise cb.Unsupported("degenerate geometry support") from error
        if simplex < 0:
            raise cb.Unsupported("geometry outside training hull")
        bary = hull.transform[simplex, :d] @ (p - hull.transform[simplex, d])
        weights = np.append(bary, 1 - bary.sum())
        selected = hull.simplices[simplex]
    if np.any(weights < 0):
        raise cb.Unsupported("negative interpolation weights")
    models = [anchors[int(i)]["model"] for i in selected]
    model = {}
    for name, first in models[0].items():
        if name in ("port_sides", "rho_kg_m3", "sound_speed_m_s"):
            if any(m[name] != first for m in models):
                raise cb.Unsupported("fluid or modal ordering differs across anchors")
            model[name] = first
        else:
            arrays = [np.asarray(m[name], dtype=float) for m in models]
            if any(a.shape != arrays[0].shape for a in arrays):
                raise cb.Unsupported("common basis/output dimensions differ")
            model[name] = sum(w * a for w, a in zip(weights, arrays))
    return model, [anchors[int(i)]["candidate"] for i in selected]


def structural_curve(model, query):
    k, m, c, b, l = (np.asarray(model[name]) for name in ("K", "M", "C", "B", "L"))
    curve = [
        l @ np.linalg.solve(k - omega**2 * m + 1j * omega * c, b)
        for omega in 2 * np.pi * np.asarray(query["frequency_hz"])
    ]
    return {
        "response_real": np.asarray(curve)[:, :, 0].real.tolist(),
        "response_imag": np.asarray(curve)[:, :, 0].imag.tolist(),
        "static_m_per_n": (l @ np.linalg.solve(k, b))[:, 0].tolist(),
    }


def acoustic_curve(model, query):
    """exp(+i omega t), L2-orthonormal port modes, outgoing decaying branch."""
    k, m, c, v = (np.asarray(model[name]) for name in ("K", "M", "C", "ports"))
    cutoff, rho, sound = (
        np.asarray(model["cutoff_m_inv"]),
        model["rho_kg_m3"],
        model["sound_speed_m_s"],
    )
    incident = np.asarray(query["incident_real"]) + 1j * np.asarray(
        query["incident_imag"]
    )
    outlet = np.asarray(model["port_sides"]) == "outlet"
    tl, balance, mode_counts = [], [], []
    for omega, a in zip(2 * np.pi * np.asarray(query["frequency_hz"]), incident):
        kz = np.conj(np.sqrt((omega / sound) ** 2 - cutoff**2 + 0j))
        if np.any((kz.real <= 0) & (np.abs(a) > 0)):
            raise cb.Unsupported(
                "incident evanescent/cutoff mode has no registered power drive"
            )
        radiation = (v * (kz / rho)) @ v.T
        u = np.linalg.solve(
            k - omega**2 * m + 1j * omega * c + 1j * radiation, 2j * v @ (kz * a / rho)
        )
        outgoing = v.T @ u - a
        power = kz.real / (2 * rho * omega)
        pin = float(np.sum(power * np.abs(a) ** 2))
        transmitted = float(np.sum(power[outlet] * np.abs(outgoing[outlet]) ** 2))
        reflected = float(np.sum(power[~outlet] * np.abs(outgoing[~outlet]) ** 2))
        absorbed = float((np.vdot(u, c @ u) / 2).real)
        if pin <= 0 or transmitted <= 0:
            raise cb.Unsupported(
                "no finite incident/transmitted power; no arbitrary dB floor"
            )
        tl.append(10 * math.log10(pin / transmitted))
        balance.append((pin - transmitted - reflected - absorbed) / pin)
        mode_counts.append(int(np.count_nonzero(kz.real > 0)))
    return {"tl_db": tl}, {
        "relative_power_residual": balance,
        "propagating_modes": mode_counts,
        "frequency_systems": len(tl),
    }


def reduce_observables(family, query, observed, reducers):
    result = {}
    for r in reducers:
        kind = r["kind"]
        if kind == "input_scalar":
            value = query["input_scalars"][r["quantity"]]
        elif kind in ("dynamic_peak", "static_peak"):
            curve = (
                (
                    np.asarray(observed["response_real"])
                    + 1j * np.asarray(observed["response_imag"])
                )
                if kind == "dynamic_peak"
                else np.asarray(observed["static_m_per_n"])
            )
            value = float(np.max(np.abs(curve))) * (1000 if r["unit"] == "mm/N" else 1)
        elif kind == "interval_p10_tl_db":
            value = pb.interval_p10(query["frequency_hz"], observed["tl_db"])
        else:
            value = float(np.min(observed["tl_db"]))
        if not math.isfinite(value):
            raise cb.Unsupported("nonfinite reduced observable")
        result[r["quantity"]] = float(value)
    return result


def predict(export, verified):
    if not isinstance(verified, Operators):
        raise TypeError("validated Operators required")
    body = verified.body
    family, rows = body["family"], body["rows"]
    predictions, folds, screen, reasons, errors, acoustic = {}, [], [], [], [], []
    for coordinates in sorted({tuple(r["coordinates"]) for r in rows}):
        held = [r for r in rows if tuple(r["coordinates"]) == coordinates]
        training = [r for r in rows if tuple(r["coordinates"]) != coordinates]
        folds.append(
            {
                "held_action_coordinates": list(coordinates),
                "held_rows": len(held),
                "training_rows": len(training),
                "held_geometry_operators_used": False,
            }
        )
        for target in held:
            t0, c0 = time.perf_counter(), time.process_time()
            start = None
            fit_cost = query_cost = None
            key = None, target["candidate"], target["condition"]
            try:
                peers = [
                    r
                    for r in training
                    if r["context_sha256"] == target["context_sha256"]
                    and r["observer_version"] == target["observer_version"]
                ]
                model, anchors = interpolate(peers, target)
                start = time.perf_counter(), time.process_time()
                fit_cost = {"wall_s": start[0] - t0, "cpu_s": start[1] - c0}
                if family == "f08":
                    output = structural_curve(model, target["query"])
                    diagnostic = None
                else:
                    output, diagnostic = acoustic_curve(model, target["query"])
                values = reduce_observables(
                    family, target["query"], output, body["reducers"]
                )
                query_cost = {
                    "wall_s": time.perf_counter() - start[0],
                    "cpu_s": time.process_time() - start[1],
                }
                predictions[key] = values
                # Witness data enter only AFTER prediction/query timing.
                if family == "f08":
                    truth = np.asarray(
                        target["witness"]["response_real"]
                    ) + 1j * np.asarray(target["witness"]["response_imag"])
                    computed = np.asarray(output["response_real"]) + 1j * np.asarray(
                        output["response_imag"]
                    )
                else:
                    truth, computed = np.asarray(
                        target["witness"]["tl_db"]
                    ), np.asarray(output["tl_db"])
                errors.append((computed - truth).ravel())
                if diagnostic is not None:
                    acoustic.append(
                        {
                            "candidate": target["candidate"],
                            "condition": target["condition"],
                            "anchors": anchors,
                            **diagnostic,
                        }
                    )
            except (cb.Unsupported, np.linalg.LinAlgError) as error:
                reason = (
                    str(error)
                    if isinstance(error, cb.Unsupported)
                    else "singular reduced query; reference status unchanged"
                )
                reasons.append(
                    {
                        "candidate": target["candidate"],
                        "condition": target["condition"],
                        "reason": reason,
                    }
                )
                if start is None:
                    fit_cost = {
                        "wall_s": time.perf_counter() - t0,
                        "cpu_s": time.process_time() - c0,
                    }
                else:
                    query_cost = {
                        "wall_s": time.perf_counter() - start[0],
                        "cpu_s": time.process_time() - start[1],
                    }
            screen.append(
                {
                    "candidate": target["candidate"],
                    "condition": target["condition"],
                    "status": "PREDICTED" if key in predictions else "ABSTAINED",
                    "fit_cost": fit_cost,
                    "query_cost": query_cost,
                }
            )
    return predictions, {
        "folds": folds,
        "abstention_reasons": reasons,
        "curve_errors": pb._curve_errors(errors),
        "acoustic_diagnostics": acoustic,
        "screening_rows": screen,
    }


def measure(export, *, operators=None):
    producer_panels.adapt_export(export)
    if export["family"] not in ("f08", "f13"):
        raise ValueError("stronger arms own f08/f13 only")
    report = {
        "schema": "carbon.development-reduced-baseline-report.v1",
        "family": export["family"],
        "export_digest": export["export_digest"],
        "reference_solves_launched": 0,
        "carbon_arm": "NOT_SUPPLIED",
        "v4_disposition": "UNRESOLVED_NO_MATCHED_CARBON_ARM",
        "reference_adequacy": "NOT_ASSESSED_BY_COMPARATOR",
        "calibration_support": "PRODUCER_DECLARED_NOT_SCIENTIFICALLY_VERIFIED",
        "claims": {
            "physical_safety": False,
            "qualified_uncertainty": False,
            "tested_challenge": False,
            "strongest_industry_baseline_proven": False,
        },
    }
    if operators is None:
        report["held_out"] = {"status": "HOLD_MISSING_PROJECTED_OPERATORS"}
        report["equal_budget_screening"] = {
            "status": "HOLD_MISSING_PROJECTED_OPERATORS",
            "query_cost": None,
            "candidate_rankings": None,
        }
        return report
    verified = validate_operators(export, operators)
    predictions, diagnostics = predict(export, verified)
    screen = diagnostics.pop("screening_rows")
    report["scope"] = operators["scope"]
    exact = {
        (r["band"], r["candidate"], r["condition"]): r["values"]
        for r in cb._physical_rows(export)
    }
    report["closed_bank"] = {
        "interpretation": "exact lookup replay, not new-geometry performance",
        "pointwise": cb.pointwise_errors(export, exact),
        "decision": cb.decision_report(export, exact),
    }
    report["held_out"] = {
        "status": "MEASURED" if predictions else "HOLD_NO_SUPPORTED_PREDICTIONS",
        "pointwise": cb.pointwise_errors(export, predictions),
        "decision": cb.decision_report(export, predictions),
        **diagnostics,
    }
    report["operators_digest"] = operators["operators_digest"]
    report["costs"] = {
        k: {"status": "NOT_MEASURED" if v is None else "PRODUCER_REPORTED", "value": v}
        for k, v in operators["costs"].items()
    }
    report["equal_budget_screening"] = pb.screening_export(export, predictions, screen)
    report["equal_budget_screening"]["operators_digest"] = operators["operators_digest"]
    report["fold_interpretation"] = (
        "leave-whole-geometry-out; no target operators; common-basis convex interpolation inside calibrated hull; unsupported boundaries abstain"
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--operators", type=Path, required=True)
    parser.add_argument("--operators-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    t0, c0 = time.perf_counter(), time.process_time()
    report = measure(
        pb._read(args.panel, args.expected_sha256),
        operators=pb._read(args.operators, args.operators_sha256),
    )
    report.update(
        {
            "input_sha256": args.expected_sha256,
            "operators_sha256": args.operators_sha256,
            "comparator_source_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            "helper_source_sha256": {
                module.__name__: hashlib.sha256(
                    Path(module.__file__).read_bytes()
                ).hexdigest()
                for module in (pb, cb, producer_panels, tasks)
            },
            "read_validation_measure_cpu_s": time.process_time() - c0,
            "read_validation_measure_wall_s": time.perf_counter() - t0,
            "environment": {
                "canonical": False,
                "python": pb.platform.python_version(),
                "numpy": np.__version__,
                "scipy": pb.scipy.__version__,
                "platform": pb.platform.platform(),
            },
        }
    )
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, sort_keys=True, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "family": report["family"],
                "reference_solves_launched": 0,
                "output": str(args.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

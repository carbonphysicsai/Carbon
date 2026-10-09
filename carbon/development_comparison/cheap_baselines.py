"""Offline DEVELOPMENT comparators. No solver, official judge or dispatch path.

Every fitted-row prediction is separated from grouped held-out measurement.
Interpolation envelopes are descriptive, not qualified physical error bounds.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import platform
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy
from scipy.interpolate import RBFInterpolator

from carbon.design_search import indexed, producer_panels, reference_resolution, tasks


class Unsupported(ValueError):
    """Missing coverage, not a physical failure."""


@dataclass(frozen=True)
class Envelope:
    point: dict
    lower: dict
    upper: dict


def _finite_array(value, dimensions):
    result = np.asarray(value, dtype=float)
    if result.ndim != dimensions or not np.isfinite(result).all():
        raise ValueError("finite array of the declared dimension required")
    return result


class CurveSurface:
    """Vector-valued full signed-curve surface; settings fixed before folds.

    Gaussian degree-zero RBF is an ordinary-Kriging-style fixed-kernel
    comparator, not a maximum-likelihood-tuned stochastic uncertainty model.
    No candidate identifier or held-out value enters coordinates/scaling.
    """

    def __init__(self, coordinates, curves, *, kernel="gaussian"):
        if kernel not in ("gaussian", "multiquadric"):
            raise ValueError("fixed Gaussian or multiquadric comparator required")
        x, y = _finite_array(coordinates, 2), _finite_array(curves, 2)
        if len(x) != len(y) or len(x) < 2 or x.shape[1] == 0:
            raise ValueError("aligned coordinate/full-curve rows required")
        if len(np.unique(x, axis=0)) != len(x):
            raise ValueError("duplicate coordinates must be reconciled by producer")
        self.minimum, self.maximum = x.min(axis=0), x.max(axis=0)
        self.scale = np.where(
            self.maximum > self.minimum, self.maximum - self.minimum, 1
        )
        self.model = RBFInterpolator(
            (x - self.minimum) / self.scale,
            y,
            kernel=kernel,
            epsilon=1.0,
            smoothing=1e-8,
            degree=0,
        )

    def predict(self, coordinates):
        x = _finite_array(coordinates, 2)
        if x.shape[1] != len(self.minimum):
            raise ValueError("coordinate dimension differs")
        if np.any(x < self.minimum) or np.any(x > self.maximum):
            raise Unsupported("outside fitted coordinate bounds")
        return self.model((x - self.minimum) / self.scale)


def curve_observables(loaded, cogging):
    """Complete sampled-curve reductions; no between-angle truth claim."""
    loaded, cogging = _finite_array(loaded, 1), _finite_array(cogging, 1)
    if len(loaded) < 2 or len(cogging) < 2:
        raise ValueError("complete sampled curves required")
    mean = float(loaded.mean())
    if mean == 0:
        raise Unsupported("relative energized ripple undefined at zero mean")
    pk = float(np.ptp(loaded))
    return {
        "mean_nm": mean,
        "pk_pk_nm": pk,
        "ripple_fraction": pk / abs(mean),
        "cogging_nm": float(np.ptp(cogging)),
    }


class ConservativeMap:
    """Local multilinear interpolation requiring every enclosing corner.

    Switch and cooling are partitioned, never interpolated. Retained bands
    bracket temperature; endpoint bands cannot extrapolate. Corner extrema
    are a diagnostic envelope, NOT a mathematical bound on nonlinear truth.
    """

    def __init__(self, rows):
        self.rows = list(rows)
        self.cells = {}
        for row in self.rows:
            key = (row["switch_v"], row["cooling"])
            point = (row["band"], row["c1"], row["c2"])
            values = row["values"]
            _finite_array(list(values.values()), 1)
            cells = self.cells.setdefault(key, {})
            if point in cells and cells[point] != values:
                raise ValueError("conflicting physical rows")
            cells[point] = dict(values)

    def predict(self, *, band, c1, c2, switch_v, cooling):
        cells = self.cells.get((switch_v, cooling), {})
        point = (band, c1, c2)
        if point in cells:
            value = dict(cells[point])
            return Envelope(value, dict(value), dict(value))
        choices = []
        for dimension, coordinate in enumerate(point):
            values = sorted({p[dimension] for p in cells})
            lower = [v for v in values if v <= coordinate]
            upper = [v for v in values if v >= coordinate]
            if not lower or not upper:
                raise Unsupported("no bracketing support; extrapolation refused")
            intervals = [sorted({lower[-1], upper[0]})]
            strict_lower = [v for v in values if v < coordinate]
            strict_upper = [v for v in values if v > coordinate]
            if strict_lower and strict_upper:
                strict = [strict_lower[-1], strict_upper[0]]
                if strict not in intervals:
                    intervals.append(strict)
            choices.append(intervals)
        supported = [
            axes
            for axes in itertools.product(*choices)
            if all(corner in cells for corner in itertools.product(*axes))
        ]
        if not supported:
            raise Unsupported("incomplete local rectangle; nearest recipe refused")
        # Fixed coordinate-only ordering, never chosen by witness error/value.
        axes = min(supported, key=lambda a: (sum(len(x) == 2 for x in a), a))
        corners = list(itertools.product(*axes))
        quantities = set(cells[corners[0]])
        if any(set(cells[corner]) != quantities for corner in corners):
            raise ValueError("inconsistent observable coverage")
        weights = []
        for corner in corners:
            weight = 1.0
            for coordinate, endpoints, vertex in zip(point, axes, corner):
                if len(endpoints) == 2:
                    fraction = (coordinate - endpoints[0]) / (
                        endpoints[1] - endpoints[0]
                    )
                    weight *= fraction if vertex == endpoints[1] else 1 - fraction
            weights.append(weight)
        return Envelope(
            {
                q: sum(w * cells[c][q] for c, w in zip(corners, weights))
                for q in quantities
            },
            {q: min(cells[c][q] for c in corners) for q in quantities},
            {q: max(cells[c][q] for c in corners) for q in quantities},
        )


def conservative_values(task, envelope):
    """Refuse any envelope touching a registered safety/refinement band."""
    result = dict(envelope.point)
    for limit in task["limits"]:
        q = limit["quantity"]
        value = envelope.upper[q] if limit["op"] == "<=" else envelope.lower[q]
        if tasks._verdict(limit, value, True) is not True:
            raise Unsupported("diagnostic envelope does not establish safety margin")
        result[q] = value
    objective = task["objective"]
    q = objective["quantity"]
    if q not in {limit["quantity"] for limit in task["limits"]}:
        result[q] = (
            envelope.upper[q] if objective["sense"] == "min" else envelope.lower[q]
        )
    return result


def feasibility_report(task, panel, predictions, *, band, verdicts=None):
    """Point-prediction verdicts; unknown truth/support never means agreement.

    This diagnostic is separate from the conservative selection policy. It
    exposes false-feasible point predictions even when that policy abstains.
    """
    reference = {(r["candidate"], r["condition"]): r["values"] for r in panel}
    truth = (
        reference_resolution.assessed(task, reference, verdicts)
        if verdicts is not None
        else tasks.assess(task, reference, reference=True)
    )
    predicted = tasks.assess(
        task,
        {
            (r["candidate"], r["condition"]): predictions[
                (band, r["candidate"], r["condition"])
            ]
            for r in panel
            if (band, r["candidate"], r["condition"]) in predictions
        },
    )
    counts = {
        "candidates": len(truth),
        "reference_unresolved": 0,
        "prediction_unavailable": 0,
        "compared": 0,
        "agree": 0,
        "false_feasible": 0,
        "false_infeasible": 0,
    }
    for candidate in task["candidates"]:
        actual, prediction = (
            truth[candidate]["feasible"],
            predicted[candidate]["feasible"],
        )
        counts["reference_unresolved"] += actual is None
        counts["prediction_unavailable"] += prediction is None
        if actual is None or prediction is None:
            continue
        counts["compared"] += 1
        counts["agree"] += actual is prediction
        counts["false_feasible"] += prediction is True and actual is False
        counts["false_infeasible"] += prediction is False and actual is True
    return {
        **counts,
        "agreement_rate": counts["agree"] / counts["compared"]
        if counts["compared"]
        else None,
        "interpretation": "point_prediction_diagnostic_not_safety_bound",
    }


def _panels(entry):
    if entry["task"]["schema"] == tasks.INDEXED_SCHEMA:
        return [
            (index_row["index_value"], index_row["task"], reference["panel"])
            for index_row, reference in zip(
                entry["task"]["indices"], entry["reference"]
            )
        ]
    return [(None, entry["task"], entry["reference"])]


def _physical_rows(export):
    """Deduplicate requirement questions, never multiply training observations."""
    rows = {}
    for entry in export["questions"]:
        for band, task, panel in _panels(entry):
            for row in panel:
                action = task["actions"][row["candidate"]]
                key = (band, row["candidate"], row["condition"])
                record = {
                    "band": band,
                    "candidate": row["candidate"],
                    "condition": row["condition"],
                    "action": action,
                    "values": {
                        q: float(v)
                        for q, v in row["values"].items()
                        if not q.startswith("refined.")
                    },
                }
                if key in rows and rows[key] != record:
                    raise ValueError(
                        "requirement variants changed physical truth/actions"
                    )
                rows[key] = record
    return list(rows.values())


def _protocol(row):
    a = row["action"]
    return (a["c1"], a["c2"], a["switch_v"], a["cooling"])


def battery_predictions(export, *, holdout):
    """OOF predictions only: protocol removed across ALL bands, or whole band."""
    if export["family"] != "battery-v3" or holdout not in ("protocol", "band"):
        raise ValueError("battery protocol or band holdout required")
    rows = _physical_rows(export)
    groups = sorted(
        {_protocol(r) if holdout == "protocol" else r["band"] for r in rows}
    )
    predicted, envelopes, fit_cost, query_cost = {}, {}, [], []
    for group in groups:
        held = [
            r
            for r in rows
            if (_protocol(r) if holdout == "protocol" else r["band"]) == group
        ]
        train = [
            r
            for r in rows
            if (_protocol(r) if holdout == "protocol" else r["band"]) != group
        ]
        wall, cpu = time.perf_counter(), time.process_time()
        model = ConservativeMap(
            [{**r["action"], "band": r["band"], "values": r["values"]} for r in train]
        )
        fit_cost.append(
            {"cpu_s": time.process_time() - cpu, "wall_s": time.perf_counter() - wall}
        )
        wall, cpu = time.perf_counter(), time.process_time()
        for row in held:
            key = (row["band"], row["candidate"], row["condition"])
            try:
                envelope = model.predict(band=row["band"], **row["action"])
                predicted[key], envelopes[key] = envelope.point, envelope
            except Unsupported:
                continue
        query_cost.append(
            {"cpu_s": time.process_time() - cpu, "wall_s": time.perf_counter() - wall}
        )
    return (
        predicted,
        envelopes,
        {
            "folds": len(groups),
            "physical_rows": len(rows),
            "predicted_rows": len(predicted),
            "fit": _cost(fit_cost),
            "queries": _cost(query_cost),
            "held_out_unit": "whole_protocol_all_bands"
            if holdout == "protocol"
            else "whole_band",
        },
    )


MOTOR_FEATURES = (
    "magnet_mm",
    "coverage",
    "airgap_mm",
    "tooth_frac",
    "opening_frac",
    "slot_bottom_mm",
    "skew_deg",
)


def motor_predictions(export, curve_set, *, kernel):
    """Whole-geometry LODO. A digest-matched sidecar is analysis data only.

    The producer supplies physical coordinates and a complete periodic grid;
    this does not add a solver route or change its export contract.
    """
    if (
        export["family"] != "motor"
        or curve_set.get("export_digest") != export["export_digest"]
    ):
        raise ValueError("curves must bind the supplied motor export")
    if curve_set.get("sampling") != "one-period-without-repeated-endpoint":
        raise ValueError("producer must declare complete period sampling")
    if not curve_set.get("source_hashes") or not curve_set.get("observer_version"):
        raise ValueError("curve/geometry source and observer pins required")
    observers = {e["task"]["identity"]["observer_version"] for e in export["questions"]}
    if observers != {curve_set["observer_version"]}:
        raise ValueError("curve observer must match the registered motor tasks")
    grid = _finite_array(curve_set["angle_deg"], 1)
    if (
        len(grid) < 3
        or not np.all(np.diff(grid) > 0)
        or not np.allclose(np.diff(grid), grid[1] - grid[0], rtol=1e-12, atol=1e-12)
    ):
        raise ValueError("uniform complete periodic grid required by mean observer")
    rows, actual = curve_set["rows"], _physical_rows(export)
    if len(rows) != len(actual) or len({r["candidate"] for r in rows}) != len(rows):
        raise ValueError("one complete curve row per candidate required")
    if {r["candidate"] for r in rows} != {r["candidate"] for r in actual}:
        raise ValueError("curve candidate inventory differs")
    groups = {}
    actual_by_candidate = {r["candidate"]: r for r in actual}
    for r in rows:
        if set(r["coordinates"]) != set(MOTOR_FEATURES):
            raise ValueError(
                "physical geometry coordinates required; IDs are not features"
            )
        x = [r["coordinates"][name] for name in MOTOR_FEATURES]
        _finite_array(x, 1)
        for name in ("loaded_nm", "cogging_nm"):
            if len(_finite_array(r[name], 1)) != len(grid):
                raise ValueError("complete aligned loaded and cogging curves required")
        reduced = curve_observables(r["loaded_nm"], r["cogging_nm"])
        reference = actual_by_candidate[r["candidate"]]
        if any(
            not np.isclose(reduced[q], reference["values"][q], rtol=1e-12, atol=1e-12)
            for q in reduced
        ):
            raise ValueError("curve reductions differ from the bound summary observer")
        group = r["geometry_id"]
        if not isinstance(group, str) or not group:
            raise ValueError("base geometry group required")
        signature = tuple(x[:-1])
        if group in groups and groups[group] != signature:
            raise ValueError("one base geometry has inconsistent physical coordinates")
        groups[group] = signature
    if len(set(groups.values())) != len(groups):
        raise ValueError("one physical geometry split into multiple holdout groups")
    predictions, curve_errors, fits, queries = {}, [], [], []
    for group in sorted(groups):
        train = [r for r in rows if r["geometry_id"] != group]
        held = [r for r in rows if r["geometry_id"] == group]
        wall, cpu = time.perf_counter(), time.process_time()
        model = CurveSurface(
            [[r["coordinates"][name] for name in MOTOR_FEATURES] for r in train],
            [r["loaded_nm"] + r["cogging_nm"] for r in train],
            kernel=kernel,
        )
        fits.append(
            {"cpu_s": time.process_time() - cpu, "wall_s": time.perf_counter() - wall}
        )
        wall, cpu = time.perf_counter(), time.process_time()
        for r in held:
            try:
                pred = model.predict(
                    [[r["coordinates"][name] for name in MOTOR_FEATURES]]
                )[0]
                n = len(grid)
                values = curve_observables(pred[:n], pred[n:])
            except Unsupported:
                continue
            reference = actual_by_candidate[r["candidate"]]
            predictions[(None, r["candidate"], reference["condition"])] = values
            curve_errors.extend(
                (pred - np.asarray(r["loaded_nm"] + r["cogging_nm"])).tolist()
            )
        queries.append(
            {"cpu_s": time.process_time() - cpu, "wall_s": time.perf_counter() - wall}
        )
    return predictions, {
        "folds": len(groups),
        "held_out_unit": "whole_geometry_all_skews",
        "predicted_rows": len(predictions),
        "physical_rows": len(rows),
        "curve_samples": len(curve_errors),
        "curve_mae_nm": float(np.mean(np.abs(curve_errors))) if curve_errors else None,
        "curve_max_abs_nm": float(np.max(np.abs(curve_errors)))
        if curve_errors
        else None,
        "fit": _cost(fits),
        "queries": _cost(queries),
    }


def _cost(rows):
    return {
        "samples": len(rows),
        "cpu_s": sum(row["cpu_s"] for row in rows),
        "wall_s": sum(row["wall_s"] for row in rows),
        "wall_p50_s": statistics.median(row["wall_s"] for row in rows)
        if rows
        else None,
        "wall_p95_s": float(np.quantile([row["wall_s"] for row in rows], 0.95))
        if rows
        else None,
    }


def pointwise_errors(export, predictions):
    errors = {}
    rows = _physical_rows(export)
    for row in rows:
        key = (row["band"], row["candidate"], row["condition"])
        if key not in predictions:
            continue
        for q, truth in row["values"].items():
            if q in predictions[key]:
                errors.setdefault(q, []).append(predictions[key][q] - truth)
    return {
        "physical_rows": len(rows),
        "predicted_rows": len(predictions),
        "abstained_rows": len(rows) - len(predictions),
        "quantities": {
            q: {
                "samples": len(e),
                "mae": float(np.mean(np.abs(e))),
                "rmse": float(np.sqrt(np.mean(np.square(e)))),
                "max_abs": float(np.max(np.abs(e))),
            }
            for q, e in sorted(errors.items())
        },
    }


def decision_report(export, predictions, *, envelopes=None):
    """Canonical queries/commitments; no prediction repairs with held-out truth."""
    outcomes, costs, index_outcomes, comparisons, bands = [], [], [], [], {}
    for entry in export["questions"]:
        registered = entry["task"]
        query_start, cpu_start = time.perf_counter(), time.process_time()
        candidate_maps = {
            band: {tasks.digest(a): c for c, a in task["actions"].items()}
            for band, task, _ in _panels(entry)
        }

        def predict(band, task, action, condition, candidate_maps=candidate_maps):
            key = (band, candidate_maps[band][tasks.digest(action)], condition["id"])
            if envelopes is not None:
                if key not in envelopes:
                    raise Unsupported("no held-out support")
                return conservative_values(task, envelopes[key])
            if key not in predictions:
                raise Unsupported("missing prediction")
            return predictions[key]

        if registered["schema"] == tasks.INDEXED_SCHEMA:
            by_band = {row["index_value"]: row["task"] for row in registered["indices"]}
            run = indexed.run_indexed_optimizer(
                registered,
                lambda b, a, c, by_band=by_band: predict(b, by_band[b], a, c),
                model_id="development-cheap-baseline",
            )
            references = [
                {
                    "index_value": r["index_value"],
                    "values": {
                        (x["candidate"], x["condition"]): x["values"]
                        for x in r["panel"]
                    },
                }
                for r in entry["reference"]
            ]
            judge = (
                reference_resolution.judge_indexed(
                    registered, run["commitment"], references, entry["settled"]
                )
                if "settled" in entry
                else tasks.judge_indexed(registered, run["commitment"], references)
            )
            parts = [row["outcome"] for row in judge["per_index"]]
            index_outcomes.extend(parts)
            for row in judge["per_index"]:
                bands.setdefault(str(row["index_value"]), []).append(row["outcome"])
        else:
            run = tasks.run_optimizer(
                registered,
                lambda a, c, registered=registered: predict(None, registered, a, c),
                model_id="development-cheap-baseline",
            )
            reference = {
                (x["candidate"], x["condition"]): x["values"]
                for x in entry["reference"]
            }
            judge = (
                reference_resolution.judge(
                    registered, run["commitment"], reference, entry["settled"]
                )
                if "settled" in entry
                else tasks.judge(registered, run["commitment"], reference)
            )
            parts = [judge]
        feasibility = []
        settled = entry.get("settled")
        for i, (band, task, panel) in enumerate(_panels(entry)):
            verdicts = (
                settled[i]["verdicts"]
                if settled is not None and band is not None
                else settled
            )
            feasibility.append(
                {
                    "band": band,
                    **feasibility_report(
                        task, panel, predictions, band=band, verdicts=verdicts
                    ),
                }
            )
        costs.append(
            {
                "cpu_s": time.process_time() - cpu_start,
                "wall_s": time.perf_counter() - query_start,
            }
        )
        judge["exact_pick_agreement"] = all(
            p["reference_resolved"]
            and (
                p["kind"] == "CORRECT_ABSTENTION"
                or (
                    p.get("selected") is not None and p.get("selected") == p.get("best")
                )
            )
            for p in parts
        )
        judge["abstained"] = any(p["selected"] is None for p in parts)
        outcomes.append(judge)
        comparisons.append(
            {
                "question": entry["case"],
                "kind": judge["kind"],
                "reference_state": judge["reference_state"],
                "reference_resolved": judge["reference_resolved"],
                "regret": judge["regret"],
                "parts": parts,
                "feasibility": feasibility,
                "query_accounting": run["accounting"],
            }
        )
    return {
        "questions": len(outcomes),
        "summary": _agreement(outcomes),
        "pooled_band_summary": _agreement(index_outcomes) if index_outcomes else None,
        "per_band": {band: _agreement(rows) for band, rows in sorted(bands.items())},
        "decisions": comparisons,
        "query_search_and_reference_assessment": _cost(costs),
    }


def _agreement(outcomes):
    resolved = [
        o
        for o in outcomes
        if o["reference_resolved"]
        and o["kind"] not in ("SELECTED_UNRESOLVED", "ABSTENTION_UNRESOLVED")
    ]
    matches = sum(
        (o["kind"] == "CORRECT_ABSTENTION")
        or o.get("exact_pick_agreement") is True
        or (o.get("selected") is not None and o.get("selected") == o.get("best"))
        for o in resolved
    )
    priced = [o["regret"] for o in resolved if o["regret"] is not None]
    return {
        "total": len(outcomes),
        "resolved": len(resolved),
        "unresolved": len(outcomes) - len(resolved),
        "abstentions": sum(
            o.get(
                "abstained",
                o["kind"]
                in (
                    "CORRECT_ABSTENTION",
                    "MISSED_OPPORTUNITY",
                    "ABSTENTION_UNRESOLVED",
                ),
            )
            for o in outcomes
        ),
        "exact_pick_agreement_count": matches,
        "exact_pick_agreement_rate": matches / len(resolved) if resolved else None,
        "selected_infeasible": sum(
            o["kind"] == "SELECTED_INFEASIBLE" for o in outcomes
        ),
        "missed_opportunities": sum(
            o["kind"] == "MISSED_OPPORTUNITY" for o in outcomes
        ),
        "priced_regrets": len(priced),
        "mean_regret": statistics.fmean(priced) if priced else None,
    }


def measure(export, *, curve_set=None):
    """Descriptive results only; no threshold, power or portfolio disposition."""
    producer_panels.adapt_export(export)  # existing closed-shape/digest/task validation
    if export["family"] not in ("motor", "battery-v3"):
        raise ValueError("this ticket owns motor and battery-v3 only")
    exact = {
        (r["band"], r["candidate"], r["condition"]): r["values"]
        for r in _physical_rows(export)
    }
    report = {
        "schema": "carbon.development-cheap-baseline-report.v1",
        "material": "DEVELOPMENT",
        "family": export["family"],
        "export_digest": export["export_digest"],
        "carbon_arm": "NOT_SUPPLIED",
        "v4_disposition": "UNRESOLVED_NO_MATCHED_CARBON_ARM",
        "closed_bank": {
            "interpretation": "arithmetic replay, not held-out generalization",
            "pointwise": pointwise_errors(export, exact),
            "decision": decision_report(export, exact),
        },
        "unmeasured_costs": [
            "original_acquisition",
            "reference_refinement",
            "retained_solver_verification",
            "peak_process_ram",
            "licences_and_money",
            "Carbon_rebuild_inference",
        ],
        "reference_solves_launched": 0,
        "claims": {
            "physical_safety": False,
            "qualified_uncertainty": False,
            "production": False,
        },
        "method_settings": {
            "kernels": ["gaussian", "multiquadric"],
            "epsilon": 1.0,
            "smoothing": 1e-8,
            "polynomial_degree": 0,
            "motor_scaling": "training_fold_bounds_only",
            "battery_support": "complete_local_rectangle_no_extrapolation",
            "battery_discrete_partitions": ["switch_v", "cooling"],
            "selection_uncertainty": "unqualified_corner_extrema",
        },
    }
    if export["family"] == "battery-v3":
        rows = _physical_rows(export)
        report["support_inventory"] = {
            "physical_rows": len(rows),
            "rows_per_band": {
                str(b): sum(r["band"] == b for r in rows)
                for b in sorted({r["band"] for r in rows})
            },
            "cooling_levels": sorted({r["action"]["cooling"] for r in rows}),
            "rows_outside_owner_cooling_choices": sum(
                r["action"]["cooling"] not in (1, 2, 4) for r in rows
            ),
            "rows_off_owner_0_01_c_lattice": sum(
                any(
                    abs(r["action"][q] * 100 - round(r["action"][q] * 100)) > 1e-10
                    for q in ("c1", "c2")
                )
                for r in rows
            ),
            "interpretation": "existing_export_scope_not_prospective_law_adoption",
        }
    if export["family"] == "battery-v3":
        report["held_out"] = {}
        for fold in ("protocol", "band"):
            predicted, bounds, cost = battery_predictions(export, holdout=fold)
            report["held_out"][fold] = {
                "pointwise": pointwise_errors(export, predicted),
                "decision": decision_report(export, predicted, envelopes=bounds),
                "cost": cost,
                "uncertainty": "UNQUALIFIED_CORNER_ENVELOPE",
            }
    elif curve_set is not None:
        report["held_out"] = {}
        for kernel in ("gaussian", "multiquadric"):
            predicted, cost = motor_predictions(export, curve_set, kernel=kernel)
            report["held_out"][kernel] = {
                "pointwise": pointwise_errors(export, predicted),
                "decision": decision_report(export, predicted),
                "cost": cost,
                "uncertainty": "NOT_QUALIFIED",
            }
    else:
        report["held_out"] = {
            "status": "HOLD_MISSING_GEOMETRY_AND_FULL_SIGNED_CURVES",
            "reason": "ordinal design IDs are not regression coordinates",
        }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--motor-curves", type=Path)
    parser.add_argument("--curves-sha256")
    args = parser.parse_args(argv)
    if args.panel.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("bounded development panel exceeds 16 MiB")
    raw = args.panel.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.expected_sha256:
        raise ValueError("approved DEVELOPMENT input byte identity differs")
    curve_set = None
    if args.motor_curves is not None:
        if args.motor_curves.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("bounded development curve sidecar exceeds 16 MiB")
        curves_raw = args.motor_curves.read_bytes()
        if hashlib.sha256(curves_raw).hexdigest() != args.curves_sha256:
            raise ValueError("approved curve byte identity differs")
        curve_set = json.loads(curves_raw)
    elif args.curves_sha256 is not None:
        raise ValueError("curve path missing")
    report = measure(json.loads(raw), curve_set=curve_set)
    report["input_sha256"] = args.expected_sha256
    report["curve_input_sha256"] = args.curves_sha256
    report["comparator_source_sha256"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    report["environment"] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "machine": platform.machine(),
        "canonical": False,
    }
    encoded = json.dumps(report, sort_keys=True, allow_nan=False)
    if args.output is not None:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded + "\n")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "family": report["family"],
                    "reference_solves_launched": 0,
                }
            )
        )
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
